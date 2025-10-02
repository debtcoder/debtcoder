upstream api_debtcodersdoja_app {
  server 127.0.0.1:9102;
  keepalive 32;
}

server {
  listen 80;
  listen [::]:80;
  server_name api.debtcodersdoja.com;

  access_log /var/log/nginx/api.debtcodersdoja.access.log;
  error_log  /var/log/nginx/api.debtcodersdoja.error.log;

  location /.well-known/acme-challenge/ {
    root /var/www/api.debtcodersdoja.com;
  }

  location / {
    return 301 https://$host$request_uri;
  }
}

server {
  listen 443 ssl http2;
  listen [::]:443 ssl http2;
  server_name api.debtcodersdoja.com;

  access_log /var/log/nginx/api.debtcodersdoja.access.log;
  error_log  /var/log/nginx/api.debtcodersdoja.error.log;

  ssl_certificate /etc/letsencrypt/live/api.debtcodersdoja.com/fullchain.pem;
  ssl_certificate_key /etc/letsencrypt/live/api.debtcodersdoja.com/privkey.pem;
  include /etc/letsencrypt/options-ssl-nginx.conf;
  ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

  client_max_body_size 200m;
  proxy_read_timeout 120s;
  proxy_send_timeout 120s;

  location /.well-known/acme-challenge/ {
    root /var/www/api.debtcodersdoja.com;
  }

  location / {
    proxy_pass http://api_debtcodersdoja_app;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Connection "";
    proxy_buffering off;
  }
}
