import socket
import select
import threading
import urllib.request
import json
from phantomguard import config

# Maximum buffer size for parsing headers
MAX_HEADER_SIZE = 8192

def query_daemon_verify(url: str) -> bool:
    """
    Queries the local daemon to verify if a URL is allowed.
    Returns True if allowed, False if blocked.
    """
    payload = {
        "action_type": "url_fetch",
        "target": url,
        "context": "Intercepted at proxy gateway"
    }
    
    url_endpoint = f"http://{config.DAEMON_HOST}:{config.DAEMON_PORT}/verify"
    req = urllib.request.Request(
        url_endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            res_body = json.loads(res.read().decode("utf-8"))
            return res_body.get("allowed", True)
    except Exception as e:
        # Fail-secure: If daemon is offline, block URL by default
        print(f"[Proxy Warning] Failed to connect to daemon: {e}. Defaulting to BLOCK.")
        return False

def pipe_sockets(src: socket.socket, dest: socket.socket):
    """
    Pipes bidirectional data between two sockets.
    """
    sockets = [src, dest]
    try:
        while True:
            readable, _, _ = select.select(sockets, [], [], 10)
            if not readable:
                continue
            for sock in readable:
                other = dest if sock is src else src
                data = sock.recv(4096)
                if not data:
                    return
                other.sendall(data)
    except Exception:
        pass
    finally:
        try: src.close()
        except: pass
        try: dest.close()
        except: pass

def handle_client(client_socket: socket.socket):
    try:
        # Read request line & headers
        data = client_socket.recv(MAX_HEADER_SIZE)
        if not data:
            client_socket.close()
            return
            
        header_lines = data.split(b"\r\n")
        req_line = header_lines[0].decode("utf-8", errors="ignore")
        
        parts = req_line.split(" ")
        if len(parts) < 2:
            client_socket.close()
            return
            
        method, target = parts[0], parts[1]
        
        # Determine the target host and port
        if method == "CONNECT":
            # HTTPS tunnel: target is host:port
            host_port = target.split(":")
            host = host_port[0]
            port = int(host_port[1]) if len(host_port) > 1 else 443
            url_to_verify = f"https://{host}"
        else:
            # HTTP request: target is full URL (http://host/path)
            url_to_verify = target
            if not target.startswith("http"):
                url_to_verify = f"http://{target}"
            # Extract host
            if "://" in target:
                host_part = target.split("://")[1].split("/")[0]
            else:
                host_part = target.split("/")[0]
            host_port = host_part.split(":")
            host = host_port[0]
            port = int(host_port[1]) if len(host_port) > 1 else 80

        # Query the daemon for approval
        allowed = query_daemon_verify(url_to_verify)
        
        if not allowed:
            # Block and return custom HTTP response
            print(f"[Proxy Blocked] Blocked connection to: {url_to_verify}")
            block_response = (
                "HTTP/1.1 503 Service Unavailable\r\n"
                "Content-Type: text/plain\r\n"
                "Connection: close\r\n\r\n"
                "Blocked by PhantomGuard Agent Trust Firewall\r\n"
            )
            client_socket.sendall(block_response.encode("utf-8"))
            client_socket.close()
            return

        # Establish connection to target server
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.connect((host, port))
        
        if method == "CONNECT":
            # HTTPS: inform client tunnel established, then pipe raw bytes
            client_socket.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            pipe_sockets(client_socket, server_socket)
        else:
            # HTTP: send the original request line/headers to server, then pipe
            server_socket.sendall(data)
            pipe_sockets(client_socket, server_socket)
            
    except Exception as e:
        try: client_socket.close()
        except: pass

def run_proxy():
    """
    Main loop for the lightweight HTTP/HTTPS proxy server.
    """
    proxy_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    proxy_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        proxy_server.bind(("127.0.0.1", config.PROXY_PORT))
        proxy_server.listen(128)
        print(f"[Proxy] Network Interceptor Proxy listening on 127.0.0.1:{config.PROXY_PORT}...")
    except Exception as e:
        print(f"[Proxy Error] Failed to bind proxy port {config.PROXY_PORT}: {e}")
        return

    while True:
        try:
            client_sock, _ = proxy_server.accept()
            t = threading.Thread(target=handle_client, args=(client_sock,), daemon=True)
            t.start()
        except KeyboardInterrupt:
            break
        except Exception:
            pass

if __name__ == "__main__":
    run_proxy()
