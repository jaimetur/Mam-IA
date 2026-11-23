#!/bin/sh
# Arranca como root solo para dar la carpeta de datos al usuario PUID:PGID y sigue sin privilegios.
set -e
DATA="${DATA_DIR:-/data}"
mkdir -p "$DATA"
if [ "$(id -u)" = "0" ]; then
  chown -R "${PUID:-1000}:${PGID:-1000}" "$DATA" 2>/dev/null || true
  # en Synology mandan las ACL: comprobar que ese usuario puede escribir y explicarlo si no
  if ! setpriv --reuid="${PUID:-1000}" --regid="${PGID:-1000}" --clear-groups sh -c "touch '$DATA/.escritura' && rm -f '$DATA/.escritura'" 2>/dev/null; then
    echo "ERROR: el usuario ${PUID:-1000}:${PGID:-1000} no puede escribir en $DATA (carpeta del NAS montada en /data)." >&2
    echo "En Synology, pon en PUID/PGID un usuario o grupo con permiso de escritura en la ACL de esa carpeta" >&2
    echo "(por ejemplo docker_limited:docker_users, 1034:65544) o dale permiso en DSM." >&2
    exit 1
  fi
  exec setpriv --reuid="${PUID:-1000}" --regid="${PGID:-1000}" --clear-groups "$@"
fi
exec "$@"
