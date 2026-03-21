import books from './data/books.json'

interface Book {
  title: string
  author: string
  rating: number
  rating_reason: string
  url: string
}

function ratingColor(rating: number): string {
  if (rating >= 9) return 'bg-emerald-100 text-emerald-800 border-emerald-300'
  if (rating >= 7) return 'bg-sky-100 text-sky-800 border-sky-300'
  if (rating >= 5) return 'bg-amber-100 text-amber-800 border-amber-300'
  return 'bg-red-100 text-red-800 border-red-300'
}

function ratingBg(rating: number): string {
  if (rating >= 9) return 'border-l-emerald-400'
  if (rating >= 7) return 'border-l-sky-400'
  if (rating >= 5) return 'border-l-amber-400'
  return 'border-l-red-400'
}

function App() {
  const sorted = (books as Book[]).slice().sort((a, b) => b.rating - a.rating)

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      <header className="bg-white/80 backdrop-blur-sm border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-4 py-6">
          <h1 className="text-3xl font-bold text-slate-900 tracking-tight">
            Books Collection
          </h1>
          <p className="text-slate-500 mt-1">
            {sorted.length} rated books, sorted by rating
          </p>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-8">
        <div className="space-y-3">
          {sorted.map((book, i) => (
            <a
              key={i}
              href={book.url}
              target="_blank"
              rel="noopener noreferrer"
              className={`block bg-white rounded-lg border border-slate-200 border-l-4 ${ratingBg(book.rating)} shadow-sm hover:shadow-md transition-shadow p-4`}
            >
              <div className="flex items-start gap-4">
                <span
                  className={`inline-flex items-center justify-center w-11 h-11 rounded-lg border text-lg font-bold shrink-0 ${ratingColor(book.rating)}`}
                >
                  {book.rating}
                </span>
                <div className="min-w-0 flex-1">
                  <h2 className="text-base font-semibold text-slate-900 leading-snug">
                    {book.title}
                  </h2>
                  {book.author && (
                    <p className="text-sm text-slate-500 mt-0.5">{book.author}</p>
                  )}
                  <p className="text-sm text-slate-600 mt-2 leading-relaxed">
                    {book.rating_reason}
                  </p>
                </div>
              </div>
            </a>
          ))}
        </div>
      </main>
    </div>
  )
}

export default App
