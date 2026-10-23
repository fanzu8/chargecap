// ---------------------------------------------------------------------------
// chargecap - keep an always-plugged-in phone inside a charge window
//
// Licence: General Pleasure League (GPL) 1.0
//          https://github.com/fanzu8/General-Pleasure-League
//
//          You are the general of your own life, the master of your own fate:
//          no restrictions, no compulsions - use it, change it, share it, and
//          let pleasure be your primary guide.  Just be happy.
// ---------------------------------------------------------------------------

package org.chargecap.android

import android.os.SystemClock
import androidx.compose.foundation.Canvas
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.State
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.TextMeasurer
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min

// The chart, ported line for line from the GTK app's LiveChart: the same
// overlaid curves, the same per-curve auto-scaled Y axes on fixed sides, the
// same five grid divisions and the same time labels.

private const val PTS_PER_PX = 2f      // decimation cap: at most 2 drawn points per pixel
private const val GRID_DIVS = 5        // divisions of the time axis
private val TICKS = floatArrayOf(0f, 0.25f, 0.5f, 0.75f, 1f)   // 5 divisions
private const val MAX_POINTS = 4096    // hard cap on the scratch buffers

/** One live reading in a metric's own unit, or null when it is not published. */
private fun snapshotValue(s: Snapshot, key: String): Float? = when (key) {
    "voltage_v" -> s.voltageV?.toFloat()
    "current_mA" -> s.currentA?.let { (it * 1000.0).toFloat() }
    "power_w" -> s.powerW?.let { abs(it).toFloat() }
    "temp_c" -> s.tempC?.toFloat()
    "capacity" -> s.capacity?.toFloat()
    else -> null
}

/**
 * Overlays the selected metrics on one rolling chart.
 *
 * Every selected curve is auto-scaled to its own min/max so its trend stays
 * visible; its Y ticks are drawn on the left or right edge in the curve's own
 * colour.  Samples live in memory only and disappear when the app closes.
 */
@Composable
fun LiveChart(
    buffer: SampleBuffer,
    selected: List<String>,
    windowSecs: Int,
    seq: Long,
    /** The live reading, drawn as the moving head of every curve.  Reading the
     *  State inside the draw scope makes the 500 ms publisher invalidate the
     *  canvas; a stored sample is not required for the head to move. */
    tipState: State<Snapshot>,
    modifier: Modifier = Modifier,
) {
    val measurer = rememberTextMeasurer()
    val axisStyle = remember { TextStyle(fontSize = 8.sp) }
    val lineHeight = remember(measurer, axisStyle) {
        measurer.measure(AnnotatedString("0"), style = axisStyle).size.height.toFloat()
    }
    val dim = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.55f)
    val frame = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.35f)
    val grid = Color(0.5f, 0.5f, 0.5f, 0.10f)   // faint: it stays under the curves
    // scratch buffers, reused by every curve of every frame
    val xs = remember { FloatArray(MAX_POINTS + 2) }
    val vs = remember { FloatArray(MAX_POINTS + 2) }

    Canvas(modifier) {
        // Reading the live State here is what makes the canvas redraw on every
        // publish, not only when the sampler stores another point; `seq` keeps
        // identical readings redrawing too.
        val tip = tipState.value
        @Suppress("UNUSED_EXPRESSION") seq

        fun text(s: String, x: Float, y: Float, color: Color, align: String = "left") {
            val layout = measurer.measure(
                AnnotatedString(s), style = axisStyle.copy(color = color), maxLines = 1)
            val w = layout.size.width.toFloat()
            val dx = when (align) {
                "right" -> x - w
                "center" -> x - w / 2
                else -> x
            }
            drawText(layout, topLeft = Offset(dx, y))
        }

        val sel = METRICS.filter { it.key in selected }
        if (sel.isEmpty()) {
            text(tr("选择上方指标以显示曲线"), size.width / 2, size.height / 2 - lineHeight / 2,
                 dim, "center")
            return@Canvas
        }

        val padX = 2.dp.toPx()       // gap between the plot and the nearest column
        val padT = 26.dp.toPx()      // room for the two-line axis header
        val padB = 13.dp.toPx()
        val left = sel.filter { it.side == "left" }
        val right = sel.filter { it.side == "right" }
        val ph = max(10f, size.height - padT - padB)
        val top = padT
        val bottom = padT + ph
        val now = SystemClock.elapsedRealtime()
        val cutoff = now - windowSecs * 1000L
        val span = max(1.0, (now - cutoff).toDouble())

        val start = buffer.firstVisibleFrom(cutoff)
        val visible = buffer.size - start
        // the decimation cap is taken from the widget, not from the plot: the
        // plot's width is not known until the columns are, and the columns are
        // sized from ranges sampled with this stride
        val maxPoints = min(MAX_POINTS, max(2, (size.width * PTS_PER_PX).toInt()))
        // rounded up, so the scratch buffers can never be overrun by a stride
        // that falls a little short of `maxPoints`
        val step = if (visible > maxPoints) (visible + maxPoints - 1) / maxPoints else 1
        val newest = buffer.size - 1

        // Each curve's own Y range, before anything is drawn: the axis columns
        // are sized from the ticks these ranges print, and the plot takes the
        // rest.  (The sampling below recomputes the same min/max while it fills
        // the scratch buffers -- the stride is the same one.)
        val ranges = HashMap<String, Pair<Float, Float>>()
        for (m in sel) {
            if (m.fixed != null) {
                ranges[m.key] = m.fixed
                continue
            }
            var lo = Float.MAX_VALUE
            var hi = -Float.MAX_VALUE
            var last = -1
            var i = start
            while (i < buffer.size) {
                val v = buffer.valueAt(m.key, i)
                if (!v.isNaN()) {
                    if (v < lo) lo = v
                    if (v > hi) hi = v
                    last = i
                }
                i += step
            }
            if (last != newest && newest >= 0) {
                val v = buffer.valueAt(m.key, newest)
                if (!v.isNaN()) {
                    if (v < lo) lo = v
                    if (v > hi) hi = v
                }
            }
            // the live reading is part of the range: clamping the head to a
            // range made only from stored samples pinned it for a whole
            // interval after the interval changed -- a straight line until the
            // next sample widened the axis
            val liveValue = snapshotValue(tip, m.key)
            if (liveValue != null && !liveValue.isNaN()) {
                if (liveValue < lo) lo = liveValue
                if (liveValue > hi) hi = liveValue
            }
            ranges[m.key] = if (lo > hi) {
                0f to 1f
            } else {
                val pad = (hi - lo) * 0.1f
                var a = lo - pad
                var b = hi + pad
                if (b - a < 1e-9f) {
                    a -= 0.5f
                    b += 0.5f
                }
                a to b
            }
        }

        // A column is exactly as wide as what it draws: 电量's "100" needs half
        // of what 功率's "+9.28" does, and the difference is plot the fixed
        // width was leaving empty.  So the plot reaches closer to both ends.
        fun textWidth(s: String): Float =
            measurer.measure(AnnotatedString(s), axisStyle, maxLines = 1).size.width.toFloat()

        fun columnWidth(m: Metric): Float {
            val (lo, hi) = ranges.getValue(m.key)
            var w = maxOf(textWidth(metricAxisLabel(m)), textWidth(m.unit))
            for (f in TICKS) {
                w = maxOf(w, textWidth(fmt(m.format, (lo + f * (hi - lo)).toDouble())))
            }
            return w + 1f
        }

        val widths = sel.associate { it.key to columnWidth(it) }
        fun sideWidth(side: List<Metric>): Float =
            if (side.isEmpty()) 0f
            else side.sumOf { widths.getValue(it.key).toDouble() }.toFloat() + padX

        val ml = sideWidth(left)
        val mr = sideWidth(right)
        val pw = max(10f, size.width - ml - mr)

        // plot frame
        drawRect(
            color = frame,
            topLeft = Offset(ml + 0.5f, top + 0.5f),
            size = Size(pw - 1f, ph - 1f),
            style = Stroke(width = 1.dp.toPx()),
        )

        // grid: only on the tick marks, five divisions each way, very faint
        for (f in TICKS.drop(1).dropLast(1)) {
            val y = bottom - f * ph
            drawLine(grid, Offset(ml, y), Offset(ml + pw, y), strokeWidth = 0.5.dp.toPx())
        }
        for (i in 1 until GRID_DIVS) {
            val x = ml + pw * i / GRID_DIVS
            drawLine(grid, Offset(x, top), Offset(x, bottom), strokeWidth = 0.5.dp.toPx())
        }

        for (m in sel) {
            // --- collect what is visible, decimated to the plot's width ---
            var count = 0
            var last = -1
            var i = start
            while (i < buffer.size) {
                val v = buffer.valueAt(m.key, i)
                if (!v.isNaN()) {
                    xs[count] = (pw.toDouble() * (buffer.timeAt(i) - cutoff) / span).toFloat()
                    vs[count] = v
                    count++
                    last = i
                }
                i += step
            }
            // the newest sample is the most interesting one: never stride past it
            if (last != newest && newest >= 0) {
                val v = buffer.valueAt(m.key, newest)
                if (!v.isNaN()) {
                    xs[count] = (pw.toDouble() * (buffer.timeAt(newest) - cutoff) / span).toFloat()
                    vs[count] = v
                    count++
                }
            }
            // the live head: the reading now, at the right edge.  It is a dot,
            // not the last point of the path: joining it would stretch one
            // straight line across the whole interval, which is exactly the
            // line that looked frozen after changing the sampling interval.
            // The stored curve ends at the newest stored sample; the dot is
            // the value now, and the range above includes it.
            val (lo, hi) = ranges.getValue(m.key)
            val head = snapshotValue(tip, m.key)?.takeIf { !it.isNaN() }
            if (count == 0 && head == null) continue
            val k = ph / (hi - lo)

            // the curve, from stored samples only
            if (count > 0) {
                val path = Path()
                for (n in 0 until count) {
                    val x = ml + xs[n]
                    val y = bottom - (vs[n] - lo) * k
                    if (n == 0) path.moveTo(x, y) else path.lineTo(x, y)
                }
                drawPath(path, m.color, style = Stroke(width = 0.6.dp.toPx()))
            }
            // ... and the separate live head, so a curve with only one stored
            // point still shows that it is alive
            if (head != null) {
                drawCircle(m.color, radius = 1.6.dp.toPx(),
                           center = Offset(ml + pw, bottom - (head - lo) * k))
            }

            // this curve's own Y axis, on its fixed side: name over unit, then
            // five ticks down the side of the plot
            val col = if (m.side == "left") left.indexOf(m) else right.indexOf(m)
            val align = if (m.side == "left") "right" else "left"
            val before = (if (m.side == "left") left else right).take(col)
                .sumOf { widths.getValue(it.key).toDouble() }.toFloat()
            val ax = if (m.side == "left") ml - padX - before
            else size.width - mr + padX + before
            text(metricAxisLabel(m), ax, 0f, m.color, align)
            text(m.unit, ax, lineHeight, m.color, align)
            for (f in TICKS) {
                val y = when {
                    f >= 1f -> top + 1f
                    f <= 0f -> bottom - lineHeight - 1f
                    else -> bottom - f * ph - lineHeight / 2
                }
                text(fmt(m.format, (lo + f * (hi - lo)).toDouble()), ax, y, m.color, align)
            }
        }

        // time axis: a label on every division, so the spacing reads as even.
        // A label that would touch its neighbour is left out, which only
        // happens on a very narrow plot or a very long window.
        var prevStart: Float? = null
        for (f in TICKS.reversed()) {
            val s = fmtOffset(windowSecs * (1.0 - f))
            val w = measurer.measure(AnnotatedString(s), style = axisStyle, maxLines = 1)
                .size.width.toFloat()
            val x = min(max(ml, ml + pw * f - w / 2), ml + pw - w)
            if (prevStart != null && x + w > prevStart - 6f) continue
            text(s, x, size.height - lineHeight, dim, "left")
            prevStart = x
        }
    }
}

/**
 * A time offset as M:SS (under an hour) or H:MM, plus 现在 at zero.
 *
 * One shape for the whole axis: the window's own dropdown says which of the
 * two units a chart is using.
 */
private fun fmtOffset(secs: Double): String {
    if (secs < 0.5) return tr("现在")
    val total = (secs + 0.5).toInt()
    return if (total < 3600) "-%d:%02d".format(total / 60, total % 60)
    else "-%d:%02d".format(total / 3600, total % 3600 / 60)
}
