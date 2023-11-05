# Requirements

- Power Shell
- Docker Desktop

# Installing

Open a powershell terminal

Execute the next command
```shell
docker compose up --build -d
```

# Running

In Docker desktop confirm that you have de `ninemanga-crawler - ninemanga.app` already running, if it is not, start it.

Execute the next command:
```shell
docker exec -it ninemanga.app python cli.py
```