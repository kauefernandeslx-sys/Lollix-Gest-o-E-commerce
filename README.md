# LOLLIX GESTÃO — projeto inicial

Aplicação web com interface React + Vite e API Python (FastAPI). O visual usa uma identidade roxa, menu lateral e painel responsivo.

## Estrutura
- `frontend/`: interface web.
- `backend/`: API Python inicial.

## Executar no navegador usando GitHub Codespaces ou outro ambiente de desenvolvimento

### 1. Interface
No terminal, execute:
```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0
```
Abra a porta 5173 quando o ambiente oferecer a opção de visualizar a aplicação.

### 2. API Python (em outro terminal)
```bash
cd backend
python -m pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
Documentação da API: `/docs` na porta 8000.

## Importante
Esta é uma base visual e técnica inicial. Os indicadores, pedidos e gráficos apresentados na tela são dados fictícios de demonstração, não dados reais da Lollix. Antes de uso operacional, implementar autenticação, banco de dados, permissões, auditoria, backups e validação com a empresa. As integrações com Magazord, gateway e sistemas internos dependem de documentação, credenciais e autorização de acesso. Não coloque senhas ou tokens no código.

A logo exibida é provisória (letra L). Substituir pelo arquivo oficial da marca quando disponível.
