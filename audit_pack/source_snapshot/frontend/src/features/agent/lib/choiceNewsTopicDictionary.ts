import choiceNewsTopicsCatalog from "../../../../../config/choice_news_topics.json";

type ChoiceNewsTopicCatalog = {
  catalog_version: string;
  groups: Array<{
    group_id: string;
    group_name: string;
    is_core: boolean;
    tags?: string[];
    topics: Array<{
      topic_code: string;
      topic_name: string;
    }>;
  }>;
};

type ChoiceNewsTopicPresentationArgs = {
  groupId: string;
  topicCode: string;
};

export type ChoiceNewsTopicPresentation = {
  displayPair: string;
  rawPair: string;
  groupName: string | null;
  topicName: string | null;
  groupTags: string[];
  groupIsCore: boolean;
  usesFallback: boolean;
};

const topicCatalog = choiceNewsTopicsCatalog as ChoiceNewsTopicCatalog;

const groupsById = new Map(
  topicCatalog.groups.map((group) => [
    group.group_id,
    {
      groupId: group.group_id,
      groupName: group.group_name,
      groupIsCore: group.is_core,
      groupTags: group.tags ?? [],
      topicsByCode: new Map(
        group.topics.map((topic) => [topic.topic_code, topic.topic_name] as const),
      ),
    },
  ]),
);

export type ChoiceNewsTopicFilterOption = {
  topicCode: string;
  label: string;
};

/** Flat topic list for filters (catalog order: group then topic). */
export function listChoiceNewsTopicFilterOptions(): ChoiceNewsTopicFilterOption[] {
  const options: ChoiceNewsTopicFilterOption[] = [];
  for (const group of topicCatalog.groups) {
    for (const topic of group.topics) {
      options.push({
        topicCode: topic.topic_code,
        label: `${group.group_name} / ${topic.topic_name}`,
      });
    }
  }
  return options.sort((a, b) => a.label.localeCompare(b.label, "zh-CN"));
}

export function getChoiceNewsTopicPresentation({
  groupId,
  topicCode,
}: ChoiceNewsTopicPresentationArgs): ChoiceNewsTopicPresentation {
  const rawPair = `${groupId} / ${topicCode}`;
  const group = groupsById.get(groupId);
  const topicName = group?.topicsByCode.get(topicCode) ?? null;
  const usesFallback = !group || !topicName;

  return {
    displayPair: usesFallback ? rawPair : `${group.groupName} / ${topicName}`,
    rawPair,
    groupName: group?.groupName ?? null,
    topicName,
    groupTags: group?.groupTags ?? [],
    groupIsCore: group?.groupIsCore ?? false,
    usesFallback,
  };
}
