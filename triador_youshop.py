#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Protótipo: Triador Operacional & Escudo Anti-Chargeback — YouShop
Autor: João Carlos Minozzi
Contexto: Desafio de Inovação – Programa de Estágio YouShop 2027 (Operações - Automação e IA)

Funcionalidades:
1. Sanitização LGPD (mascaramento de CPF, e-mail, telefone e nomes antes do processamento).
2. Detecção de risco P1 (ameaça de chargeback/contestação bancária) com escalonamento humano obrigatório.
3. Classificação de persona (Comprador, Creator Iniciante, Creator Ativo) e roteamento de fila.
4. Recuperação de guias reais da Central de Ajuda (ajuda.youshop.co) e Área de Compras.
5. Suporte opcional a LLM (via GEMINI_API_KEY) com fallback 100% determinístico e auditável.
6. Geração automática de log JSON e painel HTML para apresentação.
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib import error, request


# ==============================================================================
# 1. BASE DE CONHECIMENTO REAL MAPEADA (ajuda.youshop.co & Área de Compras)
# ==============================================================================
BASE_CONHECIMENTO: list[dict[str, Any]] = [
    {
        "id": "KB-01",
        "categoria": "Afiliados/Creators",
        "titulo": "Como criar meu link 2YOU",
        "url": "https://ajuda.youshop.co/",
        "palavras_chave": ["link", "2you", "divulgação", "personalizado", "afiliado", "creator", "comecei agora"],
        "resumo_oficial": (
            "No menu 'Meu link na Bio' ou dentro da aba 'Afiliações' no app YouShop Creators, "
            "você seleciona o produto aprovado e gera seu link exclusivo e rastreável (2YOU) para divulgação."
        ),
    },
    {
        "id": "KB-02",
        "categoria": "Afiliados/Creators",
        "titulo": "Como cadastrar minha rede social",
        "url": "https://ajuda.youshop.co/",
        "palavras_chave": ["rede social", "redes sociais", "instagram", "tiktok", "perfil", "vitrine", "aceitam"],
        "resumo_oficial": (
            "Acesse Perfil > Redes Sociais no app YouShop Creators e adicione seus canais ativos. "
            "Manter as redes sociais cadastradas é essencial para que as marcas avaliem sua presença online "
            "e aprovem solicitações na Vitrine."
        ),
    },
    {
        "id": "KB-03",
        "categoria": "Inicie aqui",
        "titulo": "Como validar sua conta na YouShop (KYC e Saque)",
        "url": "https://ajuda.youshop.co/",
        "palavras_chave": ["saque", "sacar", "validação", "validar", "cpf", "documento", "rg", "carteira", "bloqueado"],
        "resumo_oficial": (
            "Você pode se afiliar e vender normalmente, mas para liberar saques de comissões na Carteira "
            "é obrigatório concluir a validação de identidade enviando documento oficial e CPF válido no Perfil."
        ),
    },
    {
        "id": "KB-04",
        "categoria": "Afiliados/Creators",
        "titulo": "Como solicitar e acompanhar uma afiliação",
        "url": "https://ajuda.youshop.co/",
        "palavras_chave": ["afiliação", "afiliei", "retorno", "em análise", "aprovação", "marca", "vitrine"],
        "resumo_oficial": (
            "Em 'Minhas Afiliações', acompanhe o status entre Aprovadas, Em análise e Reprovadas. "
            "Marcas com aprovação manual avaliam o perfil do creator antes de liberar o link."
        ),
    },
    {
        "id": "KB-05",
        "categoria": "Produtos, Ofertas e Checkout",
        "titulo": "Como solicitar o reembolso de um produto e acompanhar pedido",
        "url": "https://customer.youshop.com.br/login",
        "palavras_chave": ["reembolso", "cancelado", "cancelar", "estorno", "prazo", "comprovante", "suplemento"],
        "resumo_oficial": (
            "Acompanhe o status da compra e o comprovante de estorno diretamente na Área de Compras "
            "(https://customer.youshop.com.br/login) usando o e-mail cadastrado no pedido. "
            "Após a aprovação do estorno, o prazo de crédito depende da operadora do cartão ou meio de pagamento."
        ),
    },
    {
        "id": "KB-06",
        "categoria": "Atendimento ao Comprador",
        "titulo": "Acompanhamento de pedido, e-mail de confirmação e papel da YouShop",
        "url": "https://customer.youshop.com.br/login",
        "palavras_chave": ["e-mail", "confirmação", "pedido", "rastrear", "rastreio", "entrega", "vendedor"],
        "resumo_oficial": (
            "A YouShop atua como intermediadora/processadora de pagamentos e infraestrutura tecnológica; "
            "a logística de envio e rastreio é realizada pelo produtor/vendedor responsável pela oferta. "
            "Mesmo sem o e-mail de confirmação na caixa de entrada, você pode consultar sua compra em "
            "https://customer.youshop.com.br/login."
        ),
    },
]


# ==============================================================================
# 2. CONJUNTO DE TESTE REAL (5 RECLAMAÇÕES PÚBLICAS ANONIMIZADAS - NOV/2026)
# ==============================================================================
CASOS_REAIS_ANONIMIZADOS: list[dict[str, str]] = [
    {
        "id": "RA-01",
        "data": "09/11/2026",
        "canal": "Reclame Aqui (Simulando entrada de atendimento)",
        "titulo": "Preciso saber o prazo e como funciona o reembolso de um suplemento cancelado",
        "mensagem": (
            "Boa tarde, tudo bem? Minha tia realizou uma compra, mas precisou cancelar e solicitar "
            "o reembolso referente a compra de um suplemento. Qual é o prazo para a solicitação ser concluída? "
            "E como funciona o processo de reembolso?"
        ),
    },
    {
        "id": "RA-02",
        "data": "06/11/2026",
        "canal": "Reclame Aqui (Simulando entrada de atendimento)",
        "titulo": "Não tive retorno sobre a afiliação que fiz no dia 30",
        "mensagem": (
            "Oi, tudo bem? Me afiliei a uma marca no dia 30 e ainda não tive retorno sobre. "
            "Quero saber se aconteceu alguma coisa e como podemos resolver isso. "
            "Aguardo retorno com urgência e preferencialmente pelo WhatsApp."
        ),
    },
    {
        "id": "RA-03",
        "data": "05/11/2026",
        "canal": "Reclame Aqui (Simulando entrada de atendimento)",
        "titulo": "Não consigo realizar saque e não me aceitam na vitrine de afiliados",
        "mensagem": (
            "Boa noite, infelizmente não estou conseguindo realizar o saque e também vi que "
            "não estão me aceitando na vitrine de afiliados. Gostaria de uma resolução desse problema."
        ),
    },
    {
        "id": "RA-04",
        "data": "05/11/2026",
        "canal": "Reclame Aqui (Simulando entrada de atendimento)",
        "titulo": "Ajuda com o link",
        "mensagem": (
            "Olá! Tudo bem? Comecei agora nesse mundo de creator e preciso de ajuda com o link da 2YOU. "
            "Entre em contato para tirar algumas dúvidas, como adicionar redes sociais, links personalizados, etc. "
            "Não tive retorno até o momento."
        ),
    },
    {
        "id": "RA-05",
        "data": "04/11/2026",
        "canal": "Reclame Aqui (Simulando entrada de atendimento)",
        "titulo": "Não recebi e-mail de confirmação do meu pedido e não tenho retorno",
        "mensagem": (
            "Boa tarde! Fiz a compra com vocês, mas não recebi o e-mail de confirmação. O que houve? "
            "Quero saber como acompanhar meu pedido e rastrear, pois é a primeira vez que compro assim "
            "e estou muito insegura. Tentei contato no whatsapp, mas não tive retorno até o momento. "
            "Se eu não tiver retorno o mais breve possível vou contestar direto com o banco."
        ),
    },
]


# ==============================================================================
# 3. CAMADA DE PRIVACIDADE E SEGURANÇA (LGPD PII MASKING)
# ==============================================================================
def sanitizar_lgpd(texto: str) -> tuple[str, list[str]]:
    """
    Remove/mascara dados pessoais identificáveis (PII) antes de enviar o texto
    para modelos de IA ou logs operacionais.
    """
    mascaras_aplicadas: list[str] = []
    sanitizado = texto

    padroes = [
        (r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b", "[CPF_OCULTO]", "CPF"),
        (r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", "[EMAIL_OCULTO]", "E-mail"),
        (r"(?:\+55\s?)?(?:\(?\d{2}\)?\s?)?(?:9\d{4}|\d{4})-?\d{4}\b", "[TELEFONE_OCULTO]", "Telefone"),
        (
            r"\b(?:Oi|Olá|Meu nome é|Sou)\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+)\b",
            "Olá [NOME_OCULTO]",
            "Nome próprio",
        ),
    ]

    for regex, substituto, rotulo in padroes:
        novo_texto, qtd = re.subn(regex, substituto, sanitizado)
        if qtd > 0:
            sanitizado = novo_texto
            mascaras_aplicadas.append(f"{rotulo} ({qtd}x)")

    return sanitizado, mascaras_aplicadas


# ==============================================================================
# 4. MOTOR DE BUSCA NA BASE OFICIAL + REGRAS DE RISCO E ROTEAMENTO
# ==============================================================================
def buscar_guias_relevantes(texto: str, top_k: int = 2) -> list[dict[str, Any]]:
    """Pontua os artigos da Central de Ajuda por sobreposição lexical e similaridade."""
    texto_lower = texto.lower()
    pontuados: list[tuple[float, dict[str, Any]]] = []

    for artigo in BASE_CONHECIMENTO:
        hits = sum(1 for kw in artigo["palavras_chave"] if kw in texto_lower)
        sim = SequenceMatcher(None, texto_lower[:160], artigo["titulo"].lower()).ratio()
        score = hits * 2.0 + sim
        if hits > 0 or sim > 0.25:
            pontuados.append((score, artigo))

    pontuados.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in pontuados[:top_k]]


def detectar_risco_chargeback(texto: str) -> tuple[bool, list[str]]:
    """Detecta sinais explícitos de contestação bancária, estorno forçado ou disputa."""
    gatilhos_criticos = [
        "contestar",
        "contestação",
        "com o banco",
        "no banco",
        "estorno no cartão",
        "chargeback",
        "procon",
        "golpe",
        "fraude",
        "não reconheço",
    ]
    texto_lower = texto.lower()
    encontrados = [g for g in gatilhos_criticos if g in texto_lower]
    return len(encontrados) > 0, encontrados


def enriquecer_com_gemini_opcional(texto_sanitizado: str, rascunho_base: str) -> tuple[str, str]:
    """
    Se GEMINI_API_KEY estiver configurada no ambiente, refina a redação usando
    exclusivamente o texto já anonimizado e a resposta ancorada nos guias oficiais.
    Caso contrário, mantém o rascunho determinístico 100% auditável.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return rascunho_base, "Determinístico (Offline / Auditável)"

    endpoint = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash:generateContent?key={api_key}"
    )
    prompt = (
        "Você é um assistente de triagem interna da equipe de Operações da YouShop. "
        "Reescreva de forma acolhedora, clara e objetiva a resposta abaixo para um analista revisar antes de enviar. "
        "REGRAS ESTRITAS: Não invente prazos numéricos que não estejam no texto base; "
        "mantenha os links oficiais exatamente como fornecidos; não solicite dados sensíveis.\n\n"
        f"Mensagem do usuário (anonimizada): {texto_sanitizado}\n\n"
        f"Base oficial aprovada:\n{rascunho_base}"
    )

    payload = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
    req = request.Request(endpoint, data=payload, headers={"Content-Type": "application/json"}, method="POST")

    try:
        with request.urlopen(req, timeout=8) as resp:
            dados = json.loads(resp.read().decode("utf-8"))
            texto_ia = dados["candidates"][0]["content"]["parts"][0]["text"].strip()
            return texto_ia, "Híbrido (Regras + Gemini 2.5 Flash)"
    except (error.URLError, KeyError, IndexError, TimeoutError):
        return rascunho_base, "Determinístico (Fallback automático)"


def classificar_ticket(caso: dict[str, str]) -> dict[str, Any]:
    """Executa a triagem completa: LGPD -> Risco P1 -> Persona/Fila -> Guia Oficial -> Rascunho."""
    texto_bruto = f"{caso.get('titulo', '')}. {caso.get('mensagem', '')}".strip()
    texto_limpo, mascaras_lgpd = sanitizar_lgpd(texto_bruto)
    texto_lower = texto_limpo.lower()

    risco_cb, gatilhos_cb = detectar_risco_chargeback(texto_limpo)
    guias = buscar_guias_relevantes(texto_limpo, top_k=2)

    # Identificação de Persona e Fila Destino
    if any(k in texto_lower for k in ["saque", "sacar", "vitrine"]):
        persona = "Creator (Bloqueio Operacional/Comercial)"
        fila = "Operações (Validação KYC) + Comercial (Vitrine)"
        prioridade = "P2 - ALTA"
        acao = "REVISAO_HUMANA_COM_CHECKLIST"
        motivo_roteamento = "Saque depende de validação KYC (CPF/documento) e vitrine depende de análise comercial/perfil."
    elif any(k in texto_lower for k in ["afiliação", "afiliei", "dia 30", "sem retorno"]):
        persona = "Creator (Aguardando Aprovação)"
        fila = "Operações / Suporte Técnico (Onboarding)"
        prioridade = "P2 - ALTA"
        acao = "VERIFICAR_LOG_CADASTRO_E_COBRAR_MARCA"
        motivo_roteamento = "Solicitação parada fora do prazo normal; verificar falha de sincronização ou pendência do produtor."
    elif any(k in texto_lower for k in ["2you", "comecei agora", "link", "rede social", "redes sociais"]):
        persona = "Creator Iniciante"
        fila = "Autoatendimento / Deflexão FAQ"
        prioridade = "P3 - NORMAL (Candidato a Deflexão)"
        acao = "SUGERIR_RESPOSTA_FAQ_PARA_APROVACAO"
        motivo_roteamento = "Dúvida operacional básica já documentada nos guias oficiais de Creators."
    else:
        persona = "Comprador"
        fila = "Atendimento ao Comprador (Pós-Venda)"
        prioridade = "P2 - MÉDIA"
        acao = "ORIENTAR_AREA_COMPRAS_E_VENDEDOR"
        motivo_roteamento = "Dúvida sobre acompanhamento de pedido, envio ou comprovante de reembolso."

    # Sobrescrita de segurança: Risco de Chargeback sempre assume P1 Crítica
    if risco_cb:
        prioridade = "P1 - CRÍTICA (Escudo Anti-Chargeback)"
        fila = f"Fila Prioritária Anti-Chargeback -> {fila}"
        acao = "ESCALONAMENTO_HUMANO_IMEDIATO"
        motivo_roteamento = (
            f"Risco iminente de disputa bancária detectado pelos termos: {', '.join(gatilhos_cb)}. "
            "Atuação humana imediata evita chargeback."
        )

    # Construção do rascunho de resposta ancorado exclusivamente na base oficial
    linhas_guia = "\n".join(
        f"- {g['titulo']} ({g['url']}): {g['resumo_oficial']}" for g in guias
    ) or "- Central de Ajuda YouShop (https://ajuda.youshop.co/)"

    rascunho_base = (
        "Olá! Tudo bem? Fazemos parte da equipe de atendimento da YouShop.\n\n"
        "Entendemos a sua solicitação e já direcionamos o seu caso para a fila responsável. "
        "Enquanto finalizamos a conferência interna, seguem as orientações oficiais para o seu caso:\n\n"
        f"{linhas_guia}\n\n"
        "Se precisar complementar alguma informação, basta responder por aqui (por segurança, "
        "não envie fotos de documentos ou dados bancários fora do ambiente oficial do app)."
    )

    resposta_sugerida, motor_redacao = enriquecer_com_gemini_opcional(texto_limpo, rascunho_base)

    return {
        "id": caso.get("id", "LIVE-01"),
        "data": caso.get("data", datetime.now().strftime("%d/%m/%Y")),
        "titulo": caso.get("titulo", "Atendimento ao vivo"),
        "texto_sanitizado": texto_limpo,
        "lgpd_mascaras": mascaras_lgpd if mascaras_lgpd else ["Nenhum dado sensível exposto"],
        "risco_chargeback": risco_cb,
        "gatilhos_chargeback": gatilhos_cb,
        "persona": persona,
        "prioridade": prioridade,
        "fila_destino": fila,
        "acao_operacional": acao,
        "motivo_roteamento": motivo_roteamento,
        "guias_citados": [{"id": g["id"], "titulo": g["titulo"], "url": g["url"]} for g in guias],
        "resposta_sugerida": resposta_sugerida,
        "motor_redacao": motor_redacao,
        "supervisao_humana": "OBRIGATÓRIA (IA prepara triagem; humano aprova envio/ação)",
    }


# ==============================================================================
# 5. GERADOR DE PAINEL VISUAL HTML (PARA DEMONSTRAÇÃO E SLIDES)
# ==============================================================================
def gerar_relatorio_html(resultados: list[dict[str, Any]], caminho_saida: Path) -> None:
    total = len(resultados)
    total_p1 = sum(1 for r in resultados if r["risco_chargeback"])
    total_deflexao = sum(1 for r in resultados if "P3" in r["prioridade"])
    total_guias = sum(len(r["guias_citados"]) for r in resultados)

    cards_html = []
    for r in resultados:
        badge_class = "p1" if "P1" in r["prioridade"] else ("p2" if "P2" in r["prioridade"] else "p3")
        guias_li = "".join(
            f"<li><strong>[{html.escape(g['id'])}]</strong> {html.escape(g['titulo'])} "
            f"<code>{html.escape(g['url'])}</code></li>"
            for g in r["guias_citados"]
        )
        cards_html.append(
            f"""
            <article class="card">
                <div class="card-top">
                    <div>
                        <span class="ticket-id">{html.escape(r['id'])} • {html.escape(r['data'])}</span>
                        <h3>{html.escape(r['titulo'])}</h3>
                    </div>
                    <span class="badge {badge_class}">{html.escape(r['prioridade'])}</span>
                </div>
                <div class="meta-grid">
                    <div><strong>Persona:</strong> {html.escape(r['persona'])}</div>
                    <div><strong>Fila Destino:</strong> {html.escape(r['fila_destino'])}</div>
                    <div><strong>Ação:</strong> {html.escape(r['acao_operacional'])}</div>
                    <div><strong>Auditoria LGPD:</strong> {html.escape(', '.join(r['lgpd_mascaras']))}</div>
                </div>
                <p class="motivo"><strong>Diagnóstico da Triagem:</strong> {html.escape(r['motivo_roteamento'])}</p>
                <div class="guias">
                    <strong>Guias Oficiais Ancorados:</strong>
                    <ul>{guias_li}</ul>
                </div>
                <div class="draft">
                    <div class="draft-header">
                        <span>Rascunho Gerado ({html.escape(r['motor_redacao'])})</span>
                        <span class="hitl">Human-in-the-Loop Ativo</span>
                    </div>
                    <pre>{html.escape(r['resposta_sugerida'])}</pre>
                </div>
            </article>
            """
        )

    pagina = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Triador Operacional & Escudo Anti-Chargeback — YouShop</title>
<style>
  :root {{
    --navy: #0F2942;
    --lime: #9BE000;
    --bg: #F4F6F9;
    --card: #FFFFFF;
    --text: #1E293B;
    --muted: #64748B;
    --border: #E2E8F0;
  }}
  * {{ box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
  body {{ margin: 0; background: var(--bg); color: var(--text); }}
  header {{ background: var(--navy); color: #fff; padding: 24px 32px; border-bottom: 4px solid var(--lime); }}
  header h1 {{ margin: 0 0 6px; font-size: 22px; }}
  header p {{ margin: 0; color: #CBD5E1; font-size: 14px; }}
  .container {{ max-width: 1080px; margin: 24px auto; padding: 0 20px; }}
  .kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 16px; margin-bottom: 24px; }}
  .kpi {{ background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 16px; }}
  .kpi span {{ font-size: 12px; color: var(--muted); text-transform: uppercase; font-weight: 600; }}
  .kpi strong {{ display: block; font-size: 28px; color: var(--navy); margin-top: 6px; }}
  .card {{ background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 20px; margin-bottom: 18px; }}
  .card-top {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 12px; }}
  .ticket-id {{ font-size: 12px; color: var(--muted); font-weight: 600; }}
  .card h3 {{ margin: 4px 0 0; font-size: 17px; color: var(--navy); }}
  .badge {{ padding: 6px 12px; border-radius: 999px; font-size: 12px; font-weight: 700; white-space: nowrap; }}
  .badge.p1 {{ background: #FEE2E2; color: #991B1B; border: 1px solid #FCA5A5; }}
  .badge.p2 {{ background: #FEF3C7; color: #92400E; border: 1px solid #FCD34D; }}
  .badge.p3 {{ background: #DCFCE7; color: #166534; border: 1px solid #86EFAC; }}
  .meta-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 8px 16px; background: #F8FAFC; padding: 12px; border-radius: 8px; font-size: 13px; margin-bottom: 12px; }}
  .motivo {{ font-size: 13.5px; margin: 0 0 12px; }}
  .guias {{ font-size: 13px; margin-bottom: 12px; }}
  .guias ul {{ margin: 6px 0 0; padding-left: 20px; }}
  .draft {{ border: 1px solid #CBD5E1; border-radius: 8px; overflow: hidden; }}
  .draft-header {{ background: #EEF2F6; padding: 8px 12px; font-size: 12px; font-weight: 600; display: flex; justify-content: space-between; }}
  .hitl {{ color: #0F2942; background: var(--lime); padding: 2px 8px; border-radius: 4px; }}
  pre {{ margin: 0; padding: 12px; white-space: pre-wrap; font-family: inherit; font-size: 13px; background: #FFF; line-height: 1.45; }}
</style>
</head>
<body>
  <header>
    <h1>Triador Operacional & Escudo Anti-Chargeback — YouShop</h1>
    <p>Protótipo funcional • Diagnóstico baseado em 5 casos públicos reais + Base Oficial (ajuda.youshop.co)</p>
  </header>
  <main class="container">
    <section class="kpis">
      <div class="kpi"><span>Tickets Analisados</span><strong>{total}</strong></div>
      <div class="kpi"><span>Alertas P1 Anti-Chargeback</span><strong>{total_p1}</strong></div>
      <div class="kpi"><span>Candidatos à Deflexão FAQ</span><strong>{total_deflexao}</strong></div>
      <div class="kpi"><span>Guias Oficiais Ancorados</span><strong>{total_guias}</strong></div>
    </section>
    {''.join(cards_html)}
  </main>
</body>
</html>
"""
    caminho_saida.write_text(pagina, encoding="utf-8")


# ==============================================================================
# 6. EXECUÇÃO PRINCIPAL (BATCH DOS 5 CASOS REAIS OU MODO INTERATIVO)
# ==============================================================================
def main() -> None:
    print("=" * 76)
    print(" TRIADOR OPERACIONAL & ESCUDO ANTI-CHARGEBACK — YOUSHOP (PROTÓTIPO)")
    print("=" * 76)

    if "--interativo" in sys.argv:
        print("\n[MODO INTERATIVO] Digite uma dúvida ou reclamação (ou 'sair' para encerrar):")
        while True:
            entrada = input("\nMensagem > ").strip()
            if not entrada or entrada.lower() == "sair":
                break
            resultado = classificar_ticket(
                {"id": "LIVE-TEST", "titulo": "Entrada ao vivo", "mensagem": entrada}
            )
            print(json.dumps(resultado, ensure_ascii=False, indent=2))
        return

    resultados = [classificar_ticket(caso) for caso in CASOS_REAIS_ANONIMIZADOS]

    for r in resultados:
        print(f"\n[{r['id']}] {r['titulo']}")
        print(f"  • Prioridade : {r['prioridade']}")
        print(f"  • Persona    : {r['persona']}")
        print(f"  • Fila       : {r['fila_destino']}")
        print(f"  • LGPD       : {', '.join(r['lgpd_mascaras'])}")
        print(f"  • Guias      : {', '.join(g['titulo'] for g in r['guias_citados'])}")

    pasta_atual = Path(__file__).resolve().parent
    arq_json = pasta_atual / "triagem_resultado.json"
    arq_html = pasta_atual / "painel_triagem_youshop.html"

    arq_json.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
    gerar_relatorio_html(resultados, arq_html)

    print("\n" + "=" * 76)
    print(f" Saída JSON gerada : {arq_json}")
    print(f" Painel HTML gerado: {arq_html}")
    print(" Dica: rode 'python triador_youshop.py --interativo' para testar ao vivo.")
    print("=" * 76)


if __name__ == "__main__":
    main()
