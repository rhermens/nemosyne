from nemosyne.mcp.mcp import register_mcp


def main() -> None:
    mcp = register_mcp()
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
