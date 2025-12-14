export interface PreviewWord {
  term: string
  definition?: string | null
  example?: string | null
}

export interface BatchImageResult {
  filename: string
  index: number
  status: 'success' | 'error'
  words: PreviewWord[]
  count: number
  error?: string
}

export interface BatchProgress {
  task_id: string
  total: number
  completed: number
  errors: number
  current_image: string | null
  current_index: number
  status: 'processing' | 'completed'
  results: BatchImageResult[]
}

