def build_prompt(keyword, summaries, configs):
    writer_config = configs["writer_config"]
    SECTIONS = writer_config.get("sections", [
        "Introduction", "Background", "Analysis", "Impact", "Takeaways", "FAQ", "Sources"
    ])

    sections_enum = "\n".join([f"{i+1}. {sec}" for i, sec in enumerate(SECTIONS)])
    PROMPT_SYSTEM = writer_config.get("prompt", {}).get("system", "")
    PROMPT_USER_TEMPLATE = writer_config.get("prompt", {}).get("user", "")

    user_prompt = PROMPT_USER_TEMPLATE.format(
        keyword=keyword,
        summaries=summaries,
        MIN_WORDS=writer_config.get("minWords", 1200),
        MAX_WORDS=writer_config.get("maxWords", 1400),
        SECTIONS_ENUM=sections_enum
    )
    return PROMPT_SYSTEM, user_prompt
