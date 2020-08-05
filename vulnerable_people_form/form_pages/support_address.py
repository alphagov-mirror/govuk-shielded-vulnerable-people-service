from flask import redirect, session

from .blueprint import form
from .render_utils import render_template_with_title
from .routing_utils import route_to_next_form_page
from .session_utils import form_answers, get_errors_from_session, request_form
from .validation import validate_support_address


@form.route("/support-address", methods=["POST"])
def post_support_address():
    session["form_answers"] = {
        **session.setdefault("form_answers", {}),
        "support_address": {**request_form()},
    }
    session["error_items"] = {}
    if not validate_support_address():
        return redirect("/support-address")
    return route_to_next_form_page()


@form.route("/support-address", methods=["GET"])
def get_support_address():
    return render_template_with_title(
        "support-address.html",
        previous_path="/address-lookup",
        values=form_answers().get("support_address", {}),
        **get_errors_from_session("support_address"),
    )
