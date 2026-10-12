"""Manage the current checkout's macOS user LaunchAgent."""

import argparse
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile

LABEL = "com.motiko.free-llms"


class Service:
    def __init__(self, root=None, home=None):
        self.root = Path(root or Path(__file__).resolve().parents[1]).resolve()
        self.home = Path(home or Path.home())
        self.plist = self.home / "Library/LaunchAgents" / f"{LABEL}.plist"
        self.domain = f"gui/{os.getuid()}"
        self.target = f"{self.domain}/{LABEL}"
        self.log = self.root / "logs/litellm.log"

    def launchctl(self, *args, check=True):
        result = subprocess.run(
            ["/bin/launchctl", *args], capture_output=True, text=True
        )
        if check and result.returncode:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())
        return result

    def loaded(self):
        return self.launchctl("print", self.target, check=False).returncode == 0

    def check_owner(self):
        if self.plist.exists():
            with self.plist.open("rb") as f:
                cfg = plistlib.load(f)
            if cfg.get("ProgramArguments") != [str(self.root / "run.sh")]:
                raise RuntimeError(
                    f"{self.plist} belongs to another checkout or service. "
                    "Uninstall it from its original checkout before installing this one."
                )
        elif self.loaded():
            raise RuntimeError("A service with this label is already loaded without our plist.")

    def install(self):
        self.check_owner()
        if not (self.root / ".venv/bin/litellm").is_file():
            raise RuntimeError("Run ./setup.sh before installing the service.")
        if not (self.root / ".env").is_file():
            raise RuntimeError("Create .env with ./setup.sh and add provider keys first.")
        cfg = {
            "Label": LABEL,
            "ProgramArguments": [str(self.root / "run.sh")],
            "WorkingDirectory": str(self.root),
            "EnvironmentVariables": {
                "HOME": str(self.home),
                "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
            },
            "RunAtLoad": True,
            "KeepAlive": True,
            "ThrottleInterval": 10,
            "StandardOutPath": str(self.log),
            "StandardErrorPath": str(self.log),
        }
        data = plistlib.dumps(cfg)
        # An unchanged install should not interrupt the running proxy.
        if self.plist.exists() and self.plist.read_bytes() == data:
            return
        self.plist.parent.mkdir(parents=True, exist_ok=True)
        self.log.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=self.plist.parent, delete=False) as f:
            temporary = Path(f.name)
            f.write(data)
        try:
            temporary.chmod(0o644)
            if self.loaded():
                self.launchctl("bootout", self.target)
            temporary.replace(self.plist)
        finally:
            temporary.unlink(missing_ok=True)

    def start(self, restart=False):
        self.install()
        self.launchctl("enable", self.target)
        if not self.loaded():
            self.launchctl("bootstrap", self.domain, str(self.plist))
        elif restart:
            self.launchctl("kickstart", "-k", self.target)
        else:
            self.launchctl("kickstart", self.target)
        print("Background service enabled, including at login.")
        print("Check ./service.sh status and ./service.sh logs for startup details.")

    def stop(self):
        self.check_owner()
        if not self.plist.exists():
            print("Service is not installed.")
            return
        # Persist the stop across logins; start explicitly re-enables it.
        self.launchctl("disable", self.target)
        if self.loaded():
            self.launchctl("bootout", self.target)
        print("Service stopped; automatic start at login is disabled.")

    def uninstall(self):
        self.stop()
        self.plist.unlink(missing_ok=True)
        print("LaunchAgent removed. Environment, credentials, and logs are preserved.")

    def status(self):
        result = self.launchctl("print", self.target, check=False)
        if result.returncode:
            print("Service is stopped or not installed.")
        else:
            # Show launchd's actual state, including crash/exit information.
            fields = ("state =", "pid =", "last exit code =", "runs =")
            for line in result.stdout.splitlines():
                if line.startswith("\t\t"):
                    continue
                if line.startswith("\t") and line.strip().startswith(fields):
                    print(line.strip())
        print(f"Plist: {self.plist}")
        print(f"Log: {self.log}")

    def logs(self):
        if not self.log.exists():
            raise RuntimeError("No service log yet. Start with ./service.sh start.")
        subprocess.run(["/usr/bin/tail", "-n", "100", "-F", str(self.log)], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=(
        "install", "start", "stop", "restart", "status", "logs", "uninstall"
    ))
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("Background service commands require macOS. Use ./run.sh elsewhere.")
    if os.getuid() == 0:
        parser.error("Run as your normal user, without sudo.")
    service = Service()
    try:
        if args.command in ("install", "start", "restart"):
            service.start(restart=args.command == "restart")
        else:
            getattr(service, args.command)()
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Service error: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
