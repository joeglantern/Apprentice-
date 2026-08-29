"""Entry point used by launchd. Equivalent to `ghost-agent` once the package is installed."""

from ghost_agent.app import main

if __name__ == "__main__":
    main()
