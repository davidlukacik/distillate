import sys


def main():
    if "--register" in sys.argv:
        from papers_workflow.remarkable_auth import register_interactive
        register_interactive()
        return

    from papers_workflow import config

    print("Zotero API Key:", config.ZOTERO_API_KEY[:8] + "...")
    print("Zotero User ID:", config.ZOTERO_USER_ID)
    print("reMarkable Token:", "set" if config.REMARKABLE_DEVICE_TOKEN else "not set (run --register)")
    print("To Read folder:", config.RM_FOLDER_TO_READ)
    print("Read folder:", config.RM_FOLDER_READ)
    print("Poll interval:", config.POLL_INTERVAL, "seconds")
    print()
    print("Config loaded successfully.")


if __name__ == "__main__":
    main()
