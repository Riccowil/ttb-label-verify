import { unreferencedImagesNotice } from "../copy.js";

export default function UnreferencedImagesNotice({ filenames }) {
  const message = unreferencedImagesNotice(filenames);
  if (!message) {
    return null;
  }
  return (
    <div className="unreferenced-images-notice" role="status">
      <p>{message}</p>
    </div>
  );
}
