const LABELS: Record<string, string> = {
  "space.created": "Created a space",
  "project.created": "Created the project",
  "material.uploaded": "Uploaded a material",
  "material.processed": "Material is ready",
  "material.failed": "Material processing failed",
  "tutor.message_sent": "Asked the Tutor",
  "quiz.started": "Started a quiz",
  "question.answered": "Answered a question",
  "quiz.completed": "Completed a quiz",
  "mastery.updated": "Mastery updated",
  "recommendation.created": "New recommendation",
  "recommendation.completed": "Completed a recommendation",
};

export const activityTypeLabel = (type: string) => LABELS[type] ?? type;

export const activityTypeOptions = Object.entries(LABELS).map(([value, label]) => ({ value, label }));
