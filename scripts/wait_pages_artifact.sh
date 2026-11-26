set -euo pipefail
for attempt in $(seq 1 12); do
  if metadata=$(gh api --method GET "/repos/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID/artifacts" -f name="$PAGES_ARTIFACT_NAME") &&
     jq -e --arg name "$PAGES_ARTIFACT_NAME" --arg id "$PAGES_ARTIFACT_ID" '
       [.artifacts[] | select(.name == $name)] as $matches |
       ($matches | length) == 1 and
       $matches[0].expired == false and
       ($matches[0].id | tostring) == $id
     ' <<< "$metadata" >/dev/null; then
    echo "Pages artifact $PAGES_ARTIFACT_NAME ($PAGES_ARTIFACT_ID) is visible."
    exit 0
  fi
  if [ "$attempt" -lt 12 ]; then sleep 5; fi
done
echo "::error::Pages artifact is not uniquely visible after bounded polling: $PAGES_ARTIFACT_NAME ($PAGES_ARTIFACT_ID)"
exit 1
