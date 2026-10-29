import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from './api';
afterEach(() => vi.unstubAllGlobals());
describe('API response integrity', () => {
  it('rejects successful HTTP with malformed JSON rather than reporting a saved mutation', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<html>error</html>', { status: 200 })));
    await expect(api('/leads/example', 'POST', {})).rejects.toThrow('Resultado não confirmado');
  });
  it('keeps the explicit provider failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Nenhuma mensagem enviada.' }), { status: 503 })));
    await expect(api('/leads/example/outreach', 'POST', {})).rejects.toThrow('Nenhuma mensagem enviada.');
  });
});
