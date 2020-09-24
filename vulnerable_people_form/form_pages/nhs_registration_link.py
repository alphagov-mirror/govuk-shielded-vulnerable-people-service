from flask import current_app

from vulnerable_people_form.form_pages.shared.constants import JourneyProgress
from vulnerable_people_form.form_pages.shared.render import render_template_with_title
from vulnerable_people_form.form_pages.shared.routing import dynamic_back_url
from .blueprint import form


@form.route("/nhs-registration-link", methods=["GET"])
def get_nhs_registration_link():
    return render_template_with_title(
        "nhs-registration-link.html",
        previous_path=dynamic_back_url(),
        nhs_registration_href=current_app.nhs_oidc_client.get_registration_url(JourneyProgress.NHS_NUMBER),
        continue_url="/applying-on-own-behalf"
    )
