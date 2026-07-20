export default function BatchValidationErrors({ detail }) {
  return (
    <div className="batch-errors" role="alert">
      <p className="batch-errors__message">{detail.message}</p>

      {detail.errors?.length > 0 && (
        <ul className="batch-errors__list">
          {detail.errors.map((message, index) => (
            <li key={index}>{message}</li>
          ))}
        </ul>
      )}

      {detail.row_errors?.length > 0 && (
        <table className="batch-errors__table">
          <thead>
            <tr>
              <th>Row</th>
              <th>Filename</th>
              <th>Errors</th>
            </tr>
          </thead>
          <tbody>
            {detail.row_errors.map((rowError) => (
              <tr key={rowError.row}>
                <td>{rowError.row}</td>
                <td className="mono">{rowError.filename}</td>
                <td>{rowError.errors.join(" ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
