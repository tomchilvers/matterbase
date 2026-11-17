"""Authenticated, administrator-only native inventory endpoint."""
from aiohttp import web
from homeassistant.components.http import HomeAssistantView


class InventoryView(HomeAssistantView):
    url='/api/matterbase/inventory'
    name='api:matterbase:inventory'
    requires_auth=True

    async def post(self,request):
        if not request['hass_user'].is_admin:
            return web.json_response({'error':'Administrator access is required.'},status=403)
        if request.content_type!='application/json':
            return web.json_response({'error':'Expected JSON.'},status=415)
        try:
            payload=await request.json()
        except ValueError:
            return web.json_response({"error":"Invalid JSON."},status=400)
        if (not isinstance(payload,dict) or payload.get('method') not in ('GET','POST','PUT','DELETE') or
            not isinstance(payload.get('path'),str) or len(payload['path'])>256 or
            not isinstance(payload.get('body',{}),dict)):
            return web.json_response({'error':'Invalid inventory request.'},status=400)
        inventory=request.app['hass'].data.get('matterbase',{}).get('inventory')
        if inventory is None:
            return web.json_response({'error':'Open or configure the native Matterbase integration first.'},status=503)
        try:
            result=await inventory.request(payload['method'],payload['path'],payload.get('body'))
        except OSError:
            return web.json_response({'error':'Could not save the inventory. Check Home Assistant storage and retry.'},status=503)
        return web.json_response(result)
