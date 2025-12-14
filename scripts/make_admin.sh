#!/bin/bash
# Quick script to create admin user in Docker environment

set -e

echo "=================================="
echo "PriceTracker - Create Admin User"
echo "=================================="
echo

# Check if Docker is running
if ! docker compose ps web >/dev/null 2>&1; then
    echo "❌ Error: Docker services not running"
    echo "💡 Start services with: docker compose up -d"
    exit 1
fi

# Run the script
if [ $# -eq 0 ]; then
    echo "Creating default admin user (username: admin, password: admin)"
    docker compose exec web python make_admin.py
elif [ $# -eq 1 ]; then
    echo "Making user '$1' an admin"
    docker compose exec web python make_admin.py "$1"
elif [ $# -eq 2 ]; then
    echo "Creating admin user '$1' with specified password"
    docker compose exec web python make_admin.py "$1" "$2"
else
    echo "Creating admin user '$1' with email '$3'"
    docker compose exec web python make_admin.py "$1" "$2" "$3"
fi

echo
echo "✅ Done!"
echo
