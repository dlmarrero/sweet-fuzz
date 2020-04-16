# Logging functions
# TODO cool console colors

info() {
    case "$1" in
        dbg)
            msg="Debug build: $2"
            ;;

        fuzz)
            msg="Fuzzer build: $2"
            ;;

        cov)
            msg="Coverage build: $2"
            ;;

        *)
            msg="$1"
            ;;
    esac

    echo "[INFO] $msg" 1>&2
}

# Writes an error message to stderr and exits
# USAGE:
# error [debug|fuzzer|cov] "Something went wrong!"
error() {
    case "$1" in
        dbg)
            msg="Debug build: $2"
            ;;

        fuzz)
            msg="Fuzzer build: $2"
            ;;

        cov)
            msg="Coverage build: $2"
            ;;

        *)
            msg="$1"
            ;;
    esac

    echo "[ERROR] $msg" 1>&2
    exit 1
}

