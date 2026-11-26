# Fila Inteligente YouShop

Protótipo de triagem para o atendimento da YouShop, feito para o **Desafio de Inovação, Programa de Estágio YouShop 2027** (Operações · Automação e IA).

**Demo:** https://jcminozzi.github.io/fila-inteligente-youshop/

## O problema

Hoje quem precisa de ajuda no app (comprador, creator ou produtor) sai para a Central de Ajuda no navegador ou cai direto na fila do WhatsApp. Lá, dúvida simples ("como crio meu link 2YOU?") fica na mesma fila de um comprador ameaçando contestar a compra no banco.

Nas 5 reclamações públicas mais recentes da YouShop no Reclame Aqui (nov/2026), todas foram resolvidas com nota 9 ou 10. O atendimento humano funciona; o gargalo é a espera até alguém abrir a conversa.

## O que o protótipo faz

1. **Oculta dados pessoais** (CPF, e-mail, telefone, nome) antes de qualquer análise.
2. **Marca risco de chargeback como P1**: "contestar no banco", "estorno no cartão", "golpe", "fraude" etc. levam o caso para o topo da fila humana, sem resposta automática.
3. **Manda para o time certo**: saque e vitrine para Operações (KYC) e Comercial; afiliação parada para Onboarding; pedido e reembolso para o Atendimento ao Comprador.
4. **Responde dúvida simples com o guia oficial** da Central de Ajuda. Se o cliente disser que não resolveu, o caso entra na fila humana com o resumo pronto.
5. **Prepara um rascunho** baseado só no texto dos guias oficiais. Nada é enviado sem um analista aprovar.

A triagem não libera saque, não aprova cadastro e não decide nada financeiro sozinha.

## Arquivos

| Arquivo | O que é |
|---|---|
| `index.html` | Protótipo web interativo (canal do cliente + console de Operações). Um arquivo só, sem dependências. |
| `triador_youshop.py` | Mesma triagem em Python, rodando em lote nos 5 casos reais. Gera `triagem_resultado.json` e um painel HTML. |

## Como rodar

Web: abra o `index.html` no navegador, ou use o link da demo.

Python (3.9+, só biblioteca padrão):

```bash
python triador_youshop.py               # roda os 5 casos e gera JSON + painel HTML
python triador_youshop.py --interativo  # testa mensagens ao vivo
```

Opcional: com `GEMINI_API_KEY` definida, o script usa o Gemini só para reescrever o rascunho, sempre a partir do texto já anonimizado. Sem a chave, tudo roda por regras, offline e auditável.

## Como cheguei aqui

- Instalei o app YouShop Creators como iniciante: o botão de ajuda leva para fora do app (navegador ou WhatsApp) sem nenhum filtro.
- A Central de Ajuda web já tem o "Pergunte à IA", então um chatbot de FAQ não seria novidade. A lacuna está entre o pedido de ajuda e a fila humana.
- Usei as 5 reclamações públicas do Reclame Aqui (nov/2026), sem nomes, como casos de teste.

Não tenho acesso à operação interna, então não sei que regras de triagem já existem. O diagnóstico se baseia só no que é visível de fora.

## Autor

João Carlos Minozzi, estudante de Ciência da Computação, com experiência em suporte de TI (fila e SLA) e segurança da informação (ISO 27001).

Projeto independente, sem vínculo oficial com a YouShop.
