#!/usr/bin/env zsh
read -r -d '' usage <<EOF
Usage: $(basename $0) [-h] [-d LockedDpms] [-i Image]
Use i3lock-color to lock the screen with multi-monitor support

    -h, --help        Display help and exit
    -d LockedDpms, --dpms LockedDpms
                      DPMS settings when locked (default: $dpms_locked)
    -i Image, --image Image
                      Background image (default: $image)"
EOF

ARGS=(
    --ignore-empty-password
    --pointer=default
    --composite
    --indicator
    --radius=25
    --insidecolor=383C4A00
    --insidevercolor=383C4A00
    --insidewrongcolor=ED071700
    --line-uses-inside
    --ring-width=6
    --ringcolor=D3DAE388
    --ringvercolor=D3DAE333
    --verifcolor=D3DAE300
    --veriftext=''
    --ringwrongcolor=ED0717AA
    --wrongcolor=D3DAE300
    --wrongtext=''
    --keyhlcolor=D3DAE3FF
    --bshlcolor=ED0717AA
    --separatorcolor=1A162800
    --indpos='350:1010'
    --force-clock
    --timecolor=D3DAE3FF
    --timestr='%H:%M'
    --timesize=32
    --time-align=1
    --timepos='40:1005'
    --time-font='roboto'
    --datecolor=D3DAE3FF
    --datestr='Type password to unlock'
    --datesize=20
    --date-align=1
    --datepos='40:1037'
    --date-font='roboto'
)

dpms_unlocked="$(xset q | awk '/Standby/{print $2, $4, $6}')"
dpms_locked="10 10 10"
num_monitors=$(xrandr --query | grep " connected" | wc -l)
image="$HOME/.local/share/backgrounds/i3locker-background.png"

while [[ -n "$1" ]]; do
    case "$1" in
        -h|--help)
            echo "$usage"
            exit 0
            ;;
        -d|--dpms)
            dpms_locked="$2"
            shift
            ;;
        -i|--image)
            image="$2"
            shift
            ;;
        *)
            echo "$usage"
            exit 1
    esac
    shift
done

dpms_revert () { xset dpms ${=dpms_unlocked} }
trap dpms_revert HUP INT TERM

dpms_set ()
{
    while true; do
        dpms_curr="$(xset q | awk '/Standby/{print $2, $4, $6}')"
        if [[ "$dpms_curr" != "$dpms_locked" ]]; then
            xset dpms ${=dpms_locked}
        fi
        sleep 5
    done
}

# Check if eog is installed; eog is used with compiz for fade-in/fade-out
which eog > /dev/null || eog=:

eog -f -g "$image" --class="i3lock" &
eog_pids=($!)
if (( num_monitors == 2 )); then
    eog -n -f -g "$image" --class="i3lock-1" &
    eog_pids+=$!
fi

dpms_set &
dpms_pid=$!

# ~/.multi-lock -i "$image" -a "$ARGS"
i3lock --nofork -i "$image" $ARGS

kill $eog_pids
kill $dpms_pid
dpms_revert
