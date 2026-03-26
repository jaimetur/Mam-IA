FROM nginx:1.27-alpine

WORKDIR /app

# Copia la app web estática
COPY src/ /usr/share/nginx/html/

# Puerto por defecto (puede sobrescribirse en runtime)
ENV PORT=80

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD wget -q -O - "http://127.0.0.1:${PORT}/" >/dev/null 2>&1 || exit 1

# Exponer el puerto estándar HTTP del contenedor
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
