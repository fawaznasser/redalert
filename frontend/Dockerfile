FROM node:20-alpine AS deps

WORKDIR /app/frontend
COPY frontend/package.json ./package.json
RUN npm install

FROM node:20-alpine AS builder

WORKDIR /app/frontend
COPY --from=deps /app/frontend/node_modules ./node_modules
COPY frontend /app/frontend
RUN npm run build

FROM node:20-alpine AS runner

ENV NODE_ENV=production

WORKDIR /app/frontend
COPY --from=builder /app/frontend/.next ./.next
COPY --from=builder /app/frontend/node_modules ./node_modules
COPY --from=builder /app/frontend/package.json ./package.json
COPY --from=builder /app/frontend/public ./public
COPY --from=builder /app/frontend/next.config.mjs ./next.config.mjs

EXPOSE 3000

CMD ["npm", "run", "start"]
