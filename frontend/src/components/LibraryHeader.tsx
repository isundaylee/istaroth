interface LibraryHeaderProps {
  title: string
}

function LibraryHeader({ title }: LibraryHeaderProps) {
  return <h1 className="library-header__title">{title}</h1>
}

export default LibraryHeader
