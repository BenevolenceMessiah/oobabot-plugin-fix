# -*- coding: utf-8 -*-
"""
Main entry point for the oobabot plugin.
This file's name is mandatory, and must be "script.py",
as that's how the plugin loader finds it.
"""
import importlib
import logging
import types

import gradio as gr
from oobabot import fancy_logger

from . import oobabot_constants
from . import oobabot_input_handlers
from . import oobabot_layout
from . import oobabot_worker

# can be set in settings.json with:
#   "oobabot-config_file string": "~/oobabot/config.yml",
#
# todo: verify that API extension is running
# todo: show that we're actually using the selected character
# add stable diffusion settings
# todo: wait for the bot to stop gracefully

STREAMING_PORT = 7860
# todo: find a way to get this from the config easier

params = {
    "is_tab": True,
    "activate": True,
    "config_file": "oobabot-config.yml",
}

##################################
# so, logging_colors.py, rather than using the logging module's built-in
# formatter, is monkey-patching the logging module's StreamHandler.emit.
# This is a problem for us, because we also use the logging module, but
# don't want ANSI color codes showing up in HTML.  We also don't want
# to break their logging.
#
# So, we're going to save their monkey-patched emit, reload the logging
# module, save off the "real" emit, then re-apply their monkey-patch.
#
# We need to do all this before we create the oobabot_worker, so that
# the logs created during startup are properly formatted.

# save the monkey-patched emit
hacked_emit = logging.StreamHandler.emit

# reload the logging module
importlib.reload(logging)

# create our logger early
fancy_logger.init_logging(logging.DEBUG, True)
ooba_logger = fancy_logger.get()

# manually apply the "correct" emit to each of the StreamHandlers
# that fancy_logger created
for handler in ooba_logger.handlers:
    if isinstance(handler, logging.StreamHandler):
        handler.emit = types.MethodType(logging.StreamHandler.emit, handler)

logging.StreamHandler.emit = hacked_emit

##################################

oobabot_layout_instance = oobabot_layout.OobabotLayout()
oobabot_worker_instance = oobabot_worker.OobabotWorker(
    STREAMING_PORT,
    params["config_file"],
    oobabot_layout_instance,
)

##################################
# discord token UI


def init_button_enablers(
    layout: oobabot_layout.OobabotLayout,
    token: str,
    plausible_token: bool,
) -> None:
    """
    Sets up handlers which will enable or disable buttons
    based on the state of other inputs.
    """

    # first, set up the initial state of the buttons, when the UI first loads
    def enable_when_token_plausible(component: gr.components.IOComponent) -> None:
        component.attach_load_event(
            lambda: component.update(interactive=plausible_token),
            None,
        )

    enable_when_token_plausible(layout.discord_token_save_button)
    enable_when_token_plausible(layout.ive_done_all_this_button)
    enable_when_token_plausible(layout.start_button)

    # initialize the discord invite link value
    layout.discord_invite_link_html.attach_load_event(
        lambda: layout.discord_invite_link_html.update(
            # pretend that the token is valid here if it's plausible,
            # but don't show a green check
            value=oobabot_constants.update_discord_invite_link(
                token,
                plausible_token,
                False,
                oobabot_worker_instance.bot.generate_invite_url,
            )
        ),
        None,
    )

    # turn on a handler for the token textbox which will enable
    # the save button only when the entered token looks plausible
    layout.discord_token_textbox.change(
        lambda token: layout.discord_token_save_button.update(
            interactive=oobabot_constants.token_is_plausible(token)
        ),
        inputs=[layout.discord_token_textbox],
        outputs=[
            layout.discord_token_save_button,
        ],
    )


def init_button_handlers(
    layout: oobabot_layout.OobabotLayout,
) -> None:
    """
    Sets handlers that are called when buttons are pressed
    """

    def handle_save_click(*args):
        # we've been passed the value of every input component,
        # so pass each in turn to our input handler

        results = []

        # iterate over args and input_handlers in parallel
        for new_value, handler in zip(
            args, oobabot_worker_instance.get_input_handlers().values()
        ):
            update = handler.update_component_from_event(new_value)
            results.append(update)

        oobabot_worker_instance.save_settings(params["config_file"])

        return tuple(results)

    def handle_save_discord_token(*args):
        # we've been passed the value of every input component,
        # so pass each in turn to our input handler

        # result is a tuple, convert it to a list so we can modify it
        results = list(handle_save_click(*args))

        # get the token from the settings
        token = oobabot_worker_instance.bot.settings.discord_settings.get_str(
            "discord_token"
        )
        is_token_valid = oobabot_worker_instance.bot.test_discord_token(token)

        # results has most of our updates, but we also need to provide ones
        # for the discord invite link and the "I've done all this" button
        results.append(
            layout.discord_invite_link_html.update(
                value=oobabot_constants.update_discord_invite_link(
                    token,
                    is_token_valid,
                    True,
                    oobabot_worker_instance.bot.generate_invite_url,
                )
            )
        )
        results.append(
            layout.ive_done_all_this_button.update(interactive=is_token_valid)
        )
        results.append(layout.start_button.update(interactive=is_token_valid))

        return tuple(results)

    layout.discord_token_save_button.click(
        handle_save_discord_token,
        inputs=[*oobabot_worker_instance.get_input_handlers().keys()],
        outputs=[
            *oobabot_worker_instance.get_input_handlers().keys(),
            layout.discord_invite_link_html,
            layout.ive_done_all_this_button,
            layout.start_button,
        ],
    )

    def update_available_characters():
        choices = oobabot_input_handlers.get_available_characters()
        layout.character_dropdown.update(
            choices=choices,
            interactive=True,
        )

    layout.reload_character_button.click(
        update_available_characters,
        inputs=[],
        outputs=[layout.character_dropdown],
    )

    layout.save_settings_button.click(
        handle_save_click,
        inputs=[*oobabot_worker_instance.get_input_handlers().keys()],
        outputs=[*oobabot_worker_instance.get_input_handlers().keys()],
    )

    def handle_start(*args):
        # things to do!
        # 1. save settings
        # 2. disable all the inputs
        # 3. disable the start button
        # 4. enable the stop button
        # 5. start the bot
        results = list(handle_save_click(*args))
        # the previous handler will have updated the input's values, but we also
        # want to disable them.  We can do this by merging the dicts.
        for update_dict, handler in zip(
            results, oobabot_worker_instance.get_input_handlers().values()
        ):
            update_dict.update(handler.disabled())

        # we also need to disable the start button, and enable the stop button
        results.append(layout.start_button.update(interactive=False))
        results.append(layout.stop_button.update(interactive=True))

        # now start the bot!
        oobabot_worker_instance.start()

        return list(results)

    # start button!!!!
    layout.start_button.click(
        handle_start,
        inputs=[
            *oobabot_worker_instance.get_input_handlers().keys(),
            layout.start_button,
            layout.stop_button,
        ],
        outputs=[
            *oobabot_worker_instance.get_input_handlers().keys(),
            layout.start_button,
            layout.stop_button,
        ],
    )

    def handle_stop():
        # things to do!
        # 1. stop the bot
        # 2. enable all the inputs
        # 3. enable the start button
        # 4. disable the stop button
        oobabot_worker_instance.reload()

        results = []
        for handler in oobabot_worker_instance.get_input_handlers().values():
            results.append(handler.enabled())

        results.append(layout.start_button.update(interactive=True))
        results.append(layout.stop_button.update(interactive=False))

        return tuple(results)

    # stop button!!!!
    layout.stop_button.click(
        handle_stop,
        inputs=[],
        outputs=[
            *oobabot_worker_instance.get_input_handlers().keys(),
            layout.start_button,
            layout.stop_button,
        ],
    )


##################################
# oobabooga <> extension interface


# pylint: disable=C0103
# pylint doesn't like the method name, but it's
# mandated by the extension interface
def ui() -> None:
    """
    Creates custom gradio elements when the UI is launched.
    """

    token = oobabot_worker_instance.bot.settings.discord_settings.get_str(
        "discord_token"
    )
    plausible_token = oobabot_constants.token_is_plausible(token)
    image_words = (
        oobabot_worker_instance.bot.settings.stable_diffusion_settings.get_list(
            "image_words"
        )
    )
    stable_diffusion_keywords = [str(x) for x in image_words]

    oobabot_layout_instance.layout_ui(
        get_logs=oobabot_worker_instance.get_logs,
        has_plausible_token=plausible_token,
        stable_diffusion_keywords=stable_diffusion_keywords,
    )

    # create our own handlers for every input event which will map
    # between our settings object and its corresponding UI component
    input_handlers = oobabot_worker_instance.get_input_handlers()

    # for all input components, add initialization handlers to
    # set their values from what we read from the settings file
    for component_to_setting in input_handlers.values():
        component_to_setting.init_component_from_setting()

    # sets up what happens when each button is pressed
    init_button_handlers(oobabot_layout_instance)

    # enables or disables buttons based on the state of other inputs
    init_button_enablers(oobabot_layout_instance, token, plausible_token)


# pylint: enable=C0103


def custom_css() -> str:
    """
    Returns custom CSS to be injected into the UI.
    """
    return oobabot_constants.LOG_CSS


def custom_js() -> str:
    """
    Returns custom JavaScript to be injected into the UI.
    """
    return oobabot_constants.CUSTOM_JS
