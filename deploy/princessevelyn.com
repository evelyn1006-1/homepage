server {
    server_name princessevelyn.com www.princessevelyn.com;
    client_max_body_size 2m;

    # Security headers
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;

    # Block dotfiles except Let's Encrypt well-known
    location ~* ^/\.(?!well-known/) {
        return 404;
    }

    # Block any direct PHP endpoint probes
    location ~* \.php($|/) {
        return 404;
    }

    # Block WP-related endpoints
    location ~* ^/(?:[^/]+/)?wp-(?:login\.php|admin/|content/|includes/) {
        return 404;
    }

    location ~* ^/(wp-admin|wp-login\.php|administrator|admin\.php|admin/login|adminpanel|phpmyadmin|pma|mysql|myadmin) {
        return 404;
    }

    # Block admin and API probes
    location = /admin {
        return 404;
    }
    location /admin/ {
        return 404;
    }
    location = /api {
        return 404;
    }
    location /api/ {
        return 404;
    }

    # Princess Evelyn's authenticated Internet MCP bridge. The public MCP and
    # OAuth paths are intentionally stable; the loopback service uses shorter
    # internal routes.
    location = /mcp/internet {
        proxy_pass http://127.0.0.1:8008/mcp;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_request_buffering off;
        proxy_read_timeout 180s;
        proxy_send_timeout 180s;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location = /mcp/internet/ {
        return 308 /mcp/internet;
    }

    location = /mcp/internet/health {
        proxy_pass http://127.0.0.1:8008/healthz;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location = /.well-known/oauth-protected-resource/mcp/internet {
        proxy_pass http://127.0.0.1:8008/.well-known/oauth-protected-resource/mcp/internet;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location = /.well-known/oauth-authorization-server/mcp/oauth {
        proxy_pass http://127.0.0.1:8008/.well-known/oauth-authorization-server;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location = /mcp/oauth/authorize {
        proxy_pass http://127.0.0.1:8008/authorize;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location = /mcp/oauth/token {
        proxy_pass http://127.0.0.1:8008/token;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location = /mcp/oauth/register {
        proxy_pass http://127.0.0.1:8008/register;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location = /mcp/oauth/revoke {
        proxy_pass http://127.0.0.1:8008/revoke;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location = /mcp/oauth/consent {
        proxy_pass http://127.0.0.1:8008/oauth/consent;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        proxy_pass http://127.0.0.1:8003;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    listen 443 ssl; # managed by Certbot
    ssl_certificate /etc/letsencrypt/live/princessevelyn.com/fullchain.pem; # managed by Certbot
    ssl_certificate_key /etc/letsencrypt/live/princessevelyn.com/privkey.pem; # managed by Certbot
    include /etc/letsencrypt/options-ssl-nginx.conf; # managed by Certbot
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem; # managed by Certbot


}
server {
    server_name princessevelyn.com www.princessevelyn.com;

    listen 80;
    location ^~ /.well-known/acme-challenge/ {
        root /var/www/html;
        default_type text/plain;
        try_files $uri =404;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}
