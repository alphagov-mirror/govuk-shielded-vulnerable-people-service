from vulnerable_people_form.form_pages.shared.render import render_template_with_title
from .blueprint import form


@form.route("/no-consent", methods=["GET"])
def get_nhs_login_no_consent():
    return render_template_with_title(
        "nhs-login-no-consent.html",
        previous_path="/nhs-login"
    )
