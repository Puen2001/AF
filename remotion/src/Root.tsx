import "./index.css";
import { Composition } from "remotion";
import { Short, ShortProps } from "./Short";

const defaults: ShortProps = {
  fps: 30,
  width: 1080,
  height: 1920,
  durationInFrames: 300,
  voice: "voice.mp3",
  music: null,
  words: [],
  shots: [],
};

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="Short"
      component={Short}
      defaultProps={defaults}
      // duration/size are data-driven from the props the pipeline passes
      calculateMetadata={({ props }) => ({
        durationInFrames: Math.max(props.durationInFrames || 1, 1),
        fps: props.fps || 30,
        width: props.width || 1080,
        height: props.height || 1920,
      })}
    />
  );
};
