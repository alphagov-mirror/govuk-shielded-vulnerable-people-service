from flask import redirect

from .answers_enums import YesNoAnswers, get_radio_options_from_enum
from .blueprint import form
from .render_utils import render_template_with_title
from .routing_utils import route_to_next_form_page
from .session_utils import (
    form_answers,
    get_errors_from_session,
    request_form,
    update_session_answers_from_form,
)
from .validation import validate_nhs_login


@form.route("/nhs-login", methods=["GET"])
def get_nhs_login():
    return render_template_with_title(
        "nhs-login.html",
        radio_items=get_radio_options_from_enum(
            YesNoAnswers, form_answers().get("nhs_login")
        ),
        previous_path="/",
        **get_errors_from_session("nhs_login"),
    )


@form.route("/nhs-login", methods=["POST"])
def post_nhs_login():
    update_session_answers_from_form()
    if not validate_nhs_login():
        return redirect("/nhs-login")
    return route_to_next_form_page()
