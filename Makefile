.PHONY: dev docker docker-down clean

# Local dev (no docker)
dev:
	cd backend && uvicorn main:app --reload --port 8000 &
	@sleep 2
	open frontend/index.html

# Docker (local)
docker:
	docker compose up --build -d
	@echo "Frontend: http://localhost:3000"
	@echo "API: http://localhost:8000"

docker-down:
	docker compose down

clean:
	rm -rf backend/__pycache__
