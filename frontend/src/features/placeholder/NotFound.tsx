import { Link } from 'react-router'

export function NotFound() {
  return (
    <div className="px-6 py-20 text-center">
      <h1 className="text-2xl font-semibold">Page not found</h1>
      <Link to="/story" className="mt-4 inline-block text-accent underline">
        Back to the story
      </Link>
    </div>
  )
}
