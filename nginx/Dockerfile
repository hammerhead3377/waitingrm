FROM nginx:alpine
RUN apk add --no-cache openssl
COPY nginx.conf /etc/nginx/nginx.conf
COPY openclaw.conf /etc/nginx/conf.d/default.conf
COPY www/ /var/www/openclaw/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
