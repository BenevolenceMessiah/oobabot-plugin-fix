# -*- coding: utf-8 -*-
"""
Stores constant values to display in the UI.

Including:
 - instructional markdown
 - custom css
 - custom js
"""

# import importlib.resources
import os
import pathlib
import typing

TOKEN_LEN_CHARS = 72


def resource(name: str) -> str:
    # return importlib.resources.read_text("oobabot_plugin", name)
    return pathlib.Path(os.path.join(os.path.dirname(__file__), name)).read_text()


def get_instructions_markdown() -> typing.Tuple[str, str]:
    """
    Returns markdown in two parts, before and after the
    token input box.
    """
    md_text = resource("instructions.md")
    return tuple(md_text.split("{{TOKEN_INPUT_BOX}}", 1))


def get_css() -> str:
    return resource("oobabot_log.css")


def get_js() -> str:
    return resource("oobabot_log.js")


def token_is_plausible(token: str) -> bool:
    return len(token.strip()) >= TOKEN_LEN_CHARS


def make_link_from_token(
    token: str,
    fn_calc_invite_url: typing.Optional[typing.Callable[[str], str]],
) -> str:
    if not token or not fn_calc_invite_url:
        return "A link will appear here once you have set your Discord token."
    link = fn_calc_invite_url(token)
    return (
        f'<a href="{link}" id="oobabot-invite-link" target="_blank">Click here to <pre>'
        + "invite your bot</pre> to a Discord server</a>."
    )


def update_discord_invite_link(
    new_token: str,
    is_token_valid: bool,
    is_tested: bool,
    fn_generate_invite_url: typing.Optional[typing.Callable[[str], str]],
):
    new_token = new_token.strip()
    prefix = ""
    if is_tested:
        if is_token_valid:
            prefix = "✔️ Your token is valid.<br><br>"
        else:
            prefix = "❌ Your token is invalid."
    if is_token_valid:
        return prefix + make_link_from_token(
            new_token,
            fn_generate_invite_url,
        )
    if new_token:
        return prefix
    return "A link will appear here once you have set your Discord token."
