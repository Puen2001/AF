import {
  AbsoluteFill,
  Audio,
  Easing,
  Img,
  OffthreadVideo,
  Sequence,
  Series,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

// ---- props shape (written by the Python pipeline as props.json) ----
export type Word = { text: string; start: number; end: number }; // seconds
export type Shot = {
  file?: string | null; // relative to public/ (video). null => card
  from: number; // start frame
  frames: number; // duration in frames
};
export type ShortProps = {
  fps: number;
  width: number;
  height: number;
  durationInFrames: number;
  voice: string; // public-relative
  music?: string | null;
  words: Word[];
  shots: Shot[];
  hook?: string;
};

const FONT =
  '"Anuphan","Sukhumvit Set","Noto Sans Thai","Bai Jamjuree","Thonburi",system-ui,sans-serif';
const ACCENT = "#ffe14d"; // active-word highlight

// A single footage shot: cover-cropped to vertical, with a scale-punch on the cut
// (1.08 -> 1.0 over ~7 frames) + a very slow Ken Burns drift so nothing sits static.
const Clip: React.FC<{ shot: Shot; index: number }> = ({ shot, index }) => {
  const f = useCurrentFrame();
  const punch = interpolate(f, [0, 7], [1.08, 1.0], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.ease),
  });
  const drift = interpolate(f, [0, shot.frames], [1.0, 1.06], {
    extrapolateRight: "clamp",
  });
  const scale = punch * drift;
  if (!shot.file) {
    // honest no-footage beat: a clean dark card, never random filler
    return (
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(120% 120% at 50% 40%, #161a24 0%, #0b0d12 100%)",
        }}
      />
    );
  }
  return (
    <AbsoluteFill style={{ backgroundColor: "black", overflow: "hidden" }}>
      <AbsoluteFill style={{ transform: `scale(${scale})` }}>
        <OffthreadVideo
          src={staticFile(shot.file)}
          muted
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      </AbsoluteFill>
      {/* subtle top+bottom scrim so captions always read */}
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(180deg, rgba(0,0,0,0.35) 0%, rgba(0,0,0,0) 22%, rgba(0,0,0,0) 55%, rgba(0,0,0,0.75) 100%)",
        }}
      />
    </AbsoluteFill>
  );
};

// Word-by-word caption: shows a short chunk (<=3 tokens), the currently-spoken word
// highlighted in accent + a small scale-pop. Timing comes from real edge-tts word
// offsets, so the reveal follows speech cadence, not equal spacing.
const Captions: React.FC<{ words: Word[] }> = ({ words }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  // group into chunks of up to 3 words
  const chunks: Word[][] = [];
  for (let i = 0; i < words.length; i += 3) chunks.push(words.slice(i, i + 3));
  const chunk = chunks.find(
    (c) => t >= c[0].start && t <= c[c.length - 1].end + 0.15,
  );
  if (!chunk) return null;

  return (
    <AbsoluteFill
      style={{
        justifyContent: "flex-end",
        alignItems: "center",
        paddingBottom: "26%",
      }}
    >
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "center",
          gap: "0 18px",
          maxWidth: "88%",
        }}
      >
        {chunk.map((w, i) => {
          const active = t >= w.start && t <= w.end;
          const pop = active
            ? interpolate(t, [w.start, w.start + 0.12], [1.18, 1.0], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              })
            : 1;
          return (
            <span
              key={i}
              style={{
                fontFamily: FONT,
                fontWeight: 800,
                fontSize: 96,
                lineHeight: 1.1,
                color: active ? ACCENT : "#ffffff",
                WebkitTextStroke: "10px #000",
                paintOrder: "stroke fill",
                transform: `scale(${pop})`,
                display: "inline-block",
                textShadow: "0 6px 18px rgba(0,0,0,0.6)",
              }}
            >
              {w.text}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

export const Short: React.FC<ShortProps> = (props) => {
  const { durationInFrames, voice, music, words, shots } = props;
  return (
    <AbsoluteFill style={{ backgroundColor: "black" }}>
      <Series>
        {shots.map((shot, i) => (
          <Series.Sequence key={i} durationInFrames={Math.max(shot.frames, 1)}>
            <Clip shot={shot} index={i} />
          </Series.Sequence>
        ))}
      </Series>

      {/* captions ride over the whole video, timed to word offsets */}
      <Captions words={words} />

      {/* progress hairline */}
      <ProgressBar total={durationInFrames} />

      <Audio src={staticFile(voice)} />
      {music ? (
        <Audio
          src={staticFile(music)}
          volume={(f) =>
            interpolate(
              f,
              [0, 30, durationInFrames - 45, durationInFrames],
              [0, 0.14, 0.14, 0],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
            )
          }
        />
      ) : null}
    </AbsoluteFill>
  );
};

const ProgressBar: React.FC<{ total: number }> = ({ total }) => {
  const f = useCurrentFrame();
  const w = interpolate(f, [0, total], [0, 100], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ justifyContent: "flex-end" }}>
      <div style={{ height: 8, width: `${w}%`, backgroundColor: "#ffffffcc" }} />
    </AbsoluteFill>
  );
};
