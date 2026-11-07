"""Handles credentials the way an application does: by name and by lookup, never as a literal."""

import os
import re


def read_credentials(header, settings):
    match = re.match(r"Basic (\S+)", header)
    token = match.group(1) or settings.default_token_name
    password = settings.get("db_password") or os.environ["APP_DB_PASSWORD"]
    secret = derive_key_material(token, salt=SALT_VALUE)
    api_key = self.config.api_key_provider
    return token, password, secret, api_key
