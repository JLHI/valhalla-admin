FROM ghcr.io/valhalla/valhalla:latest

COPY build_graph.sh /usr/local/bin/build_graph.sh
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
# Normalize line endings (fix Windows CRLF) for scripts and ensure executable
RUN sed -i 's/\r$//' /usr/local/bin/*.sh || true
RUN chmod +x /usr/local/bin/build_graph.sh /usr/local/bin/entrypoint.sh

# PID 1: forward build logs to container stdout so `docker logs` works
CMD ["/usr/local/bin/entrypoint.sh"]
