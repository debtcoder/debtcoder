server {
    listen 80;
    listen [::]:80;
    server_name debtcodersdojo.com www.debtcodersdojo.com;

    access_log /var/log/nginx/debtcodersdojo.access.log;
    error_log  /var/log/nginx/debtcodersdojo.error.log;

    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name debtcodersdojo.com www.debtcodersdojo.com;

    root /var/www/debtcodersdojo.com;
    index index.html;

    access_log /var/log/nginx/debtcodersdojo.access.log;
    error_log  /var/log/nginx/debtcodersdojo.error.log;

    ssl_certificate /etc/letsencrypt/live/debtcodersdojo.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/debtcodersdojo.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    location / {
        try_files $uri $uri/ =404;
    }
}
