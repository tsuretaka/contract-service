import { afterEach, describe, expect, it, vi } from 'vitest';
import { onRequest } from '../functions/api/[[path]]';

describe('Pages API proxy', () => {
  afterEach(() => vi.restoreAllMocks());

  it('forwards the API path, query, method, and body to the Worker', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (request) => {
      const forwarded = request as Request;
      expect(forwarded.url).toBe('https://contract-service-poc-api.tsuretaka.workers.dev/api/contracts?draft=1');
      expect(forwarded.method).toBe('POST');
      expect(await forwarded.text()).toBe('payload');
      return Response.json({ ok: true }, { status: 201, headers: { 'set-cookie': 'cs_admin=test; Path=/; HttpOnly' } });
    });

    const response = await onRequest({
      request: new Request('https://contract-service-poc-web.pages.dev/api/contracts?draft=1', {
        method: 'POST',
        headers: { 'content-type': 'text/plain' },
        body: 'payload'
      })
    });

    expect(fetchMock).toHaveBeenCalledOnce();
    expect(response.status).toBe(201);
    expect(response.headers.get('set-cookie')).toContain('cs_admin=test');
  });

  it('returns a JSON 502 response when the Worker cannot be reached', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('network down'));
    const response = await onRequest({ request: new Request('https://contract-service-poc-web.pages.dev/api/health') });
    expect(response.status).toBe(502);
    await expect(response.json()).resolves.toEqual({ error: 'API proxy unavailable' });
  });
});
