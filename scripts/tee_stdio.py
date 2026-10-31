import subprocess, sys, threading

log = open(
    sys.argv[1] if len(sys.argv) > 1 else "wire.log", "w"
)
p = subprocess.Popen(
    [
        sys.executable,
        "-m",
        "secondloop.mcp_server.first_server",
        "--serve",
    ],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL,
    text=True,
    bufsize=1,
)


def up():
    for line in sys.stdin:
        log.write(">> " + line)
        log.flush()
        p.stdin.write(line)
        p.stdin.flush()
    p.stdin.close()


threading.Thread(target=up, daemon=True).start()
for line in p.stdout:
    log.write("<< " + line)
    log.flush()
    sys.stdout.write(line)
    sys.stdout.flush()
