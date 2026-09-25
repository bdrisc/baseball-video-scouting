"""Guard the private deployment's authentication and database separation."""

from pathlib import Path

import yaml


class CloudFormationLoader(yaml.SafeLoader):
    pass


CloudFormationLoader.add_multi_constructor(
    "!", lambda loader, tag, node: {tag: loader.construct_scalar(node)}
)


def test_private_stack_enforces_jwt_on_all_application_routes():
    template = yaml.load(
        (Path(__file__).resolve().parents[2] / "template.private.yaml").read_text(),
        Loader=CloudFormationLoader,
    )
    resources = template["Resources"]
    api = resources["PrivateApi"]["Properties"]
    auth = api["Auth"]
    assert auth["DefaultAuthorizer"] == "PrivateJwt"
    assert auth["Authorizers"]["PrivateJwt"]["AuthorizationScopes"] == [
        "baseball-video-scouting/access"
    ]
    assert auth["Authorizers"]["PrivateJwt"]["IdentitySource"] == ("$request.header.Authorization")
    events = resources["PrivateFunction"]["Properties"]["Events"]
    for name in ("RootRoute", "ProxyRoute"):
        assert events[name]["Properties"]["Method"] == "ANY"
        assert "Auth" not in events[name]["Properties"]
    for name in ("RootPreflight", "ProxyPreflight"):
        assert events[name]["Properties"]["Method"] == "OPTIONS"
        assert events[name]["Properties"]["Auth"] == {"Authorizer": "NONE"}


def test_private_stack_uses_distinct_database_secret_and_invite_only_users():
    template = yaml.load(
        (Path(__file__).resolve().parents[2] / "template.private.yaml").read_text(),
        Loader=CloudFormationLoader,
    )
    assert (
        "private-season-wide/database-"
        in template["Parameters"]["PrivateDatabaseSecretArn"]["AllowedPattern"]
    )
    resources = template["Resources"]
    assert resources["PrivateUserPool"]["Properties"]["AdminCreateUserConfig"] == {
        "AllowAdminCreateUserOnly": True
    }
    assert resources["PrivateUserPool"]["Properties"]["MfaConfiguration"] == "ON"
    assert resources["PrivateAppClient"]["Properties"]["GenerateSecret"] is False
    assert resources["PrivateFunction"]["Properties"]["Environment"]["Variables"][
        "DB_SECRET_ARN"
    ] == {"Ref": "PrivateDatabaseSecretArn"}
