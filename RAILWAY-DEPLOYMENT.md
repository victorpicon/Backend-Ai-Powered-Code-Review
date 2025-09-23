# 🚀 Railway Deployment Guide

## **Problema Identificado**
O erro `mongodb.railway.internal:27017: [Errno -2] Name or service not known` indica que o MongoDB não está configurado corretamente no Railway.

## **Solução: Configurar MongoDB no Railway**

### **1. Deploy do Backend no Railway**
1. Acesse [Railway.app](https://railway.app)
2. Clique em "New Project" → "Deploy from GitHub repo"
3. Selecione o repositório `Backend-Ai-Powered-Code-Review`
4. Railway detectará Python e iniciará o build

### **2. Adicionar MongoDB no Railway**
1. No dashboard do Railway, clique em "New" → "Database" → "MongoDB"
2. Escolha o plano gratuito
3. Railway criará o banco automaticamente

### **3. Configurar Variáveis de Ambiente**
No dashboard do Railway, vá em "Variables" e adicione:

```bash
# MongoDB (Railway gera automaticamente)
MONGODB_URI=mongodb://mongo:27017/code_review_db

# JWT
JWT_SECRET=your_super_secret_jwt_key_here

# CORS (sua URL do Vercel)
CORS_ALLOW_ORIGINS=https://frontend-ai-powered-code-review-pjhn84buv-revems-projects.vercel.app

# AI APIs (pelo menos uma)
GEMINI_API_KEY=your_gemini_api_key
OPENAI_API_KEY=your_openai_api_key

# Opcional
GOOGLE_CLIENT_ID=your_google_client_id
```

### **4. Obter a URL do Backend**
Após o deploy, Railway fornecerá uma URL como:
`https://your-backend-name.railway.app`

## **Configuração Correta no Railway**

### **MongoDB URI no Railway**
- **Railway gera automaticamente**: `mongodb://mongo:27017/code_review_db`
- **Ou use MongoDB Atlas**: `mongodb+srv://username:password@cluster.mongodb.net/code_review_db`

### **Variáveis Obrigatórias**
```bash
MONGODB_URI=mongodb://mongo:27017/code_review_db
JWT_SECRET=your_jwt_secret_here
CORS_ALLOW_ORIGINS=https://frontend-ai-powered-code-review-pjhn84buv-revems-projects.vercel.app
GEMINI_API_KEY=your_gemini_key
```

## **Atualizar o Frontend**

Após o deploy, atualize a variável no frontend:

```env
VITE_API_URL=https://your-backend-name.railway.app
```

## **Testar a Conexão**

1. Acesse a URL do backend: `https://your-backend-name.railway.app/api/health`
2. Deve retornar: `{"status": "ok"}`
3. Teste o frontend com a nova URL

## **Troubleshooting**

### **Erro de Conexão MongoDB**
- Verifique se `MONGODB_URI` está configurada
- Confirme se o banco está ativo no Railway
- Verifique os logs do Railway

### **CORS Issues**
- Confirme `CORS_ALLOW_ORIGINS` com a URL do Vercel
- Verifique se a URL do frontend está correta

### **Build Issues**
- Verifique se `requirements.txt` está correto
- Confirme se o `start.py` está na raiz

## **Vantagens do Railway**

- ✅ Deploy automático via Git
- ✅ MongoDB integrado
- ✅ Variáveis de ambiente fáceis
- ✅ Logs em tempo real
- ✅ Plano gratuito

## **Próximos Passos**

1. **Faça commit das alterações**:
   ```bash
   git add .
   git commit -m "Fix MongoDB connection for Railway deployment"
   git push
   ```

2. **Deploy no Railway**:
   - Conecte o repositório
   - Adicione MongoDB
   - Configure as variáveis

3. **Teste a aplicação**:
   - Verifique o health check
   - Teste o frontend

O Railway é uma excelente opção para este projeto!
