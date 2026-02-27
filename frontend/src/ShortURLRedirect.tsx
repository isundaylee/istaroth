import { redirect, type LoaderFunctionArgs } from 'react-router-dom'
import type { ShortURLResponse } from './types/api'

export async function shortURLLoader({ params }: LoaderFunctionArgs): Promise<Response> {
  const { slug } = params
  if (!slug) {
    throw new Response('Invalid short URL', { status: 400 })
  }

  const res = await fetch(`/api/short-urls/${slug}`)
  if (!res.ok) {
    throw new Response('Short URL not found', { status: 404 })
  }

  const data = (await res.json()) as ShortURLResponse
  return redirect(data.target_path)
}

function ShortURLRedirect() {
  return null
}

export default ShortURLRedirect
