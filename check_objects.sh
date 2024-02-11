for i in {0..9}; do
    if diff reconstructed_l$i.obj ../objects/large-$i.obj >/dev/null; then
        :
    else
        echo "reconstructed_l$i.obj"
    fi
done

for i in {0..9}; do
    if diff reconstructed_s$i.obj ../objects/small-$i.obj >/dev/null; then
        :
    else
        echo "reconstructed_s$i.obj"
    fi
done