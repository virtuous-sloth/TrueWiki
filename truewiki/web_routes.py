import click
import logging

from aiohttp import web
from openttd_helpers import click_helper

from . import singleton
from .metadata import load_metadata
from .views import (
    edit,
    login,
    source,
    page as view_page,
    preview,
)
from .user_session import (
    SESSION_COOKIE_NAME,
    get_user_by_bearer,
)

log = logging.getLogger(__name__)
routes = web.RouteTableDef()

RELOAD_SECRET = None


@routes.get("/")
async def root(request):
    return web.HTTPFound("/en/")


@routes.get("/user/login")
async def user_login(request):
    user = get_user_by_bearer(request.cookies.get(SESSION_COOKIE_NAME))

    body = login.view(user)
    return web.Response(body=body, content_type="text/html")


@routes.get("/edit/{page:.*}")
async def edit_page(request):
    user = get_user_by_bearer(request.cookies.get(SESSION_COOKIE_NAME))
    if not user:
        return web.HTTPFound("/user/login")

    page = request.match_info["page"]
    # Don't allow path-walking
    if ".." in page:
        raise web.HTTPNotFound()

    body = edit.view(user, page)
    if body is None:
        raise web.HTTPNotFound()
    return web.Response(body=body, content_type="text/html")


@routes.post("/edit/{page:.*}")
async def edit_page_post(request):
    user = get_user_by_bearer(request.cookies.get(SESSION_COOKIE_NAME))
    if not user:
        return web.HTTPFound("/user/login")

    page = request.match_info["page"]
    # Don't allow path-walking
    if ".." in page:
        raise web.HTTPNotFound()

    payload = await request.post()
    if "page" not in payload:
        raise web.HTTPNotFound()

    if "save" in payload:
        if not edit.save(user, page, payload["page"]):
            raise web.HTTPNotFound()
        return web.HTTPFound(f"/{page}")

    if "preview" in payload:
        body = preview.view(user, page, payload["page"])
        if body is None:
            raise web.HTTPNotFound()
        return web.Response(body=body, content_type="text/html")

    raise web.HTTPNotFound()


@routes.get("/{page:.*}.mediawiki")
async def source_page(request):
    user = get_user_by_bearer(request.cookies.get(SESSION_COOKIE_NAME))

    page = request.match_info["page"]
    # Don't allow path-walking
    if ".." in page:
        raise web.HTTPNotFound()

    body = source.view(user, page)
    if body is None:
        raise web.HTTPNotFound()
    return web.Response(body=body, content_type="text/html")


@routes.get("/{page:.*}")
async def html_page(request):
    user = get_user_by_bearer(request.cookies.get(SESSION_COOKIE_NAME))

    page = request.match_info["page"]
    # Don't allow path-walking
    if ".." in page:
        raise web.HTTPNotFound()

    body = view_page.view(user, page)
    if body is None:
        raise web.HTTPNotFound()
    return web.Response(body=body, content_type="text/html")


@routes.post("/reload")
async def reload(request):
    if RELOAD_SECRET is None:
        return web.HTTPNotFound()

    data = await request.json()

    if "secret" not in data:
        return web.HTTPNotFound()

    if data["secret"] != RELOAD_SECRET:
        return web.HTTPNotFound()

    singleton.STORAGE.reload()
    load_metadata()

    return web.HTTPNoContent()


@routes.get("/healthz")
async def healthz_handler(request):
    return web.HTTPOk()


@routes.route("*", "/{tail:.*}")
async def fallback(request):
    log.warning("Unexpected URL: %s", request.url)
    return web.HTTPNotFound()


@click_helper.extend
@click.option(
    "--reload-secret",
    help="Secret to allow an index reload. Always use this via an environment variable!",
)
def click_web_routes(reload_secret):
    global RELOAD_SECRET

    RELOAD_SECRET = reload_secret
