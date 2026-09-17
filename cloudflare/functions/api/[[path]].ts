const API_ORIGIN = 'https://contract-service-poc-api.tsuretaka.workers.dev';

interface PagesContext {
  request: Request;
}

export async function onRequest({ request }: PagesContext): Promise<Response> {
  const incoming = new URL(request.url);
  const target = new URL(incoming.pathname + incoming.search, API_ORIGIN);

  try {
    return await fetch(new Request(target, request));
  } catch (cause) {
    console.error('API proxy failed', cause);
    return Response.json({ error: 'API proxy unavailable' }, { status: 502 });
  }
}
