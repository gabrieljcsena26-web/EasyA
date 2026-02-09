# Teste de calendário no Windows (Novo Outlook)

O Novo Outlook às vezes não “cria” o evento só ao abrir o `.ics`.
O fluxo mais confiável é importar o arquivo no calendário.

## 1) Gerar o `.ics` automaticamente

No PowerShell, na raiz do projeto:

```powershell
.\scripts\open-calendar.ps1
```

Ele:
- sobe o backend numa porta livre
- cria um agendamento real
- baixa o `.ics`
- tenta abrir no app padrão e também mostra o arquivo no Explorer

## 2) Importar no Novo Outlook (recomendado)

1. Abra o Outlook
2. Vá em **Calendário**
3. Procure **Adicionar calendário** → **Carregar de arquivo** (ou "Importar")
4. Selecione o arquivo `.ics` gerado
5. Escolha o calendário de destino e confirme

Depois disso o evento aparece no calendário e o lembrete (alarme) fica configurado.

## Observação sobre “alarme”

O lembrete não aparece como pop-up na hora da importação; ele vai disparar no horário do alarme configurado no evento.
