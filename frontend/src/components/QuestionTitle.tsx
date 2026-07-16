import styles from './QuestionTitle.module.css'

// The conversation question rendered as the page title. Shared by the saved
// conversation page's ask-another trigger and both pages' mid-stream states so
// the title looks identical before and after the post-``done`` navigation.
function QuestionTitle({ question }: { question: string }) {
  return <span className={styles.title}>{question}</span>
}

export default QuestionTitle
