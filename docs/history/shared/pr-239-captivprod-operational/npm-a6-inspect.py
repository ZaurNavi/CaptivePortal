import sqlite3, json
p="/opt/nginx-proxy-manager/data/database.sqlite"
con=sqlite3.connect(p)
con.row_factory=sqlite3.Row
print("USERS")
for r in con.execute("select id,name,nickname,email,is_disabled,is_deleted,roles from user order by id"):
    print(dict(r))
print("HOSTS")
for r in con.execute("select id,owner_user_id,domain_names,forward_scheme,forward_host,forward_port,certificate_id,ssl_forced,caching_enabled,block_exploits,allow_websocket_upgrade,http2_support,advanced_config,enabled from proxy_host where is_deleted=0 order by id"):
    print(dict(r))
con.close()
