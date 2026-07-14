"""Extension declaration, secrets, lifecycle hooks."""

from imperal_sdk import Extension, ChatExtension

ext = Extension(
    "wp-publisher",
    version="1.0.0",
    display_name="WP Publisher",
    description=(
        "Turns structured .docx articles into ready-to-review WordPress drafts: "
        "Gutenberg blocks, Rank Math SEO fields, Polylang language — and learns "
        "formatting rules from the user's confirmations."
    ),
    icon="icon.svg",
    actions_explicit=True,
)

chat = ChatExtension(
    ext,
    tool_name="wp_publisher",
    description="WP Publisher — parse structured .docx articles and publish WordPress drafts with SEO fields filled.",
)

# Credentials never flow through chat arguments — users paste them into the
# platform Secrets tab (auto-added because secrets are declared here).
ext.secret("wp_base_url", "WordPress site URL (https://example.com)",
           required=True, write_mode="both")(lambda: None)
ext.secret("wp_user", "WordPress username the Application Password belongs to",
           required=True, write_mode="both")(lambda: None)
ext.secret("wp_app_password", "WordPress Application Password (Users → Profile → Application Passwords)",
           required=True, write_mode="user")(lambda: None)


@ext.health_check
async def health_check(ctx) -> dict:
    """Liveness probe: report whether WordPress credentials are configured."""
    try:
        configured = all([
            await ctx.secrets.get("wp_base_url"),
            await ctx.secrets.get("wp_user"),
            await ctx.secrets.get("wp_app_password"),
        ])
    except Exception:
        configured = False
    return {"status": "ok", "wp_configured": configured}


@ext.on_install
async def on_install(ctx):
    """Greet the audit log so installs are traceable."""
    await ctx.log("WP Publisher installed", level="info")
