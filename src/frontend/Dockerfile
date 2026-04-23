FROM node:24-alpine

RUN mkdir -p /app && chown -R node:node /app
WORKDIR /app

RUN corepack enable

COPY --chown=node:node package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY --chown=node:node . .

EXPOSE 5173

USER node
CMD ["pnpm", "dev", "--host", "0.0.0.0", "--port", "5173"]
