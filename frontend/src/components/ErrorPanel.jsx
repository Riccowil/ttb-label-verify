export default function ErrorPanel({ message }) {
  return (
    <div className="error-panel" role="alert">
      <p className="error-panel__message">{message}</p>
    </div>
  );
}
