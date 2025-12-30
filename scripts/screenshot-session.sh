#!/bin/bash
# Helper script for managing screenshot sessions

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

show_help() {
    cat << EOF
Screenshot Session Manager

Usage:
    $0 login <name> <url>       - Create new session by logging in
    $0 list                     - List all saved sessions
    $0 use <name> <url> [opts]  - Take screenshot with session
    $0 help                     - Show this help

Examples:
    # Create a session
    $0 login local http://localhost:8000/admin

    # Use the session
    $0 use local http://localhost:8000/admin --full-page

    # List sessions
    $0 list

EOF
}

case "${1:-help}" in
    login)
        if [ -z "$2" ] || [ -z "$3" ]; then
            echo "Error: Session name and URL required"
            echo "Usage: $0 login <name> <url>"
            exit 1
        fi
        "$SCRIPT_DIR/screenshot.sh" --login "$2" "$3"
        ;;
    list)
        "$SCRIPT_DIR/screenshot.sh" --list-sessions
        ;;
    use)
        if [ -z "$2" ] || [ -z "$3" ]; then
            echo "Error: Session name and URL required"
            echo "Usage: $0 use <name> <url> [options]"
            exit 1
        fi
        session_name="$2"
        url="$3"
        shift 3
        "$SCRIPT_DIR/screenshot.sh" --session "$session_name" "$url" "$@"
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo "Unknown command: $1"
        show_help
        exit 1
        ;;
esac
