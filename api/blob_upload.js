import { handleUpload } from '@vercel/blob/client';

const DATASETS = new Set(['opportunities','orderbook','targets','po','podates']);

export default async function handler(request, response) {
  if (request.method !== 'POST') return response.status(405).json({ error: 'Method not allowed' });
  try {
    const body = request.body;
    const jsonResponse = await handleUpload({
      body,
      request,
      onBeforeGenerateToken: async (pathname, clientPayload) => {
        let payload = {};
        try { payload = JSON.parse(clientPayload || '{}'); } catch {}
        if (!DATASETS.has(payload.dataset)) throw new Error('Unknown dashboard dataset.');
        if (!pathname.startsWith(`incoming/${payload.dataset}/`)) throw new Error('Invalid upload pathname.');
        return {
          allowedContentTypes: [
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/octet-stream'
          ],
          addRandomSuffix: true,
          tokenPayload: JSON.stringify({ dataset: payload.dataset }),
        };
      },
      onUploadCompleted: async () => {},
    });
    return response.status(200).json(jsonResponse);
  } catch (error) {
    return response.status(400).json({ error: error?.message || String(error) });
  }
}
