from rest_framework import serializers
from accounts.models import User
from instructor.models import Coach
from posts.models import Post, PostImage, PostVideo, PlaybackId
from projects.models import Project, Prerequisite, Milestone, Team, MilestoneCompletionReport
from comments.models import CommentImage, Comment
from subscribers.models import Subscriber
from expertisefields.models import ExpertiseField, ExpertiseFieldAvatar
from tiers.models import Tier
from reacts.models import React
from chat.models import ChatRoom, Message


class CoachSerializer(serializers.ModelSerializer):
    expertise_field = serializers.StringRelatedField()
    avatar = serializers.SerializerMethodField()
    projects = serializers.SerializerMethodField()
    tier = serializers.SerializerMethodField()

    @staticmethod
    def get_projects(coach):
        return ProjectSerializer(coach.created_projects.all(), many=True).data

    @staticmethod
    def get_avatar(coach):
        if coach.avatar:
            return coach.avatar.image.url
        return None

    def get_tier(self, coach):
        user = self.context['request'].user
        if user.is_authenticated:
            if user.subscriptions.filter(coach=coach).exists():
                return user.subscriptions.filter(coach=coach).first().get_tier_display()

    class Meta:
        model = Coach
        fields = ['name', 'avatar', 'bio', 'expertise_field', 'projects', 'tier', 'surrogate']


class SubscriberSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField()
    id = serializers.SerializerMethodField()

    def get_id(self, subscriber):
        return subscriber.surrogate

    @staticmethod
    def get_avatar(sub):
        if sub.avatar:
            return sub.avatar.image.url
        return None

    class Meta:
        model = Subscriber
        fields = ['name', 'avatar', 'id']
        read_only_fields = ['id']


class UserSerializer(serializers.ModelSerializer):
    coach = CoachSerializer()
    subscriber = SubscriberSerializer()

    class Meta:
        model = User
        fields = ['username', 'email', 'is_coach', 'is_subscriber', 'coach', 'subscriber']


class UserMeSerializer(serializers.ModelSerializer):
    coach = CoachSerializer()
    subscriber = SubscriberSerializer()
    subscriber_data = serializers.SerializerMethodField()

    def get_subscriber_data(self, user):
        if not user.coach:
            return None
        sub_count = user.coach.subscribers.count()
        free_sub_count = user.coach.subscribers.filter(subscriptions__tier=Tier.FREE).count()
        tier1_sub_count = user.coach.subscribers.filter(subscriptions__tier=Tier.TIER1).count()
        tier2_sub_count = user.coach.subscribers.filter(subscriptions__tier=Tier.TIER2).count()
        return {'subscribers_count': sub_count, 'free_subscribers_count': free_sub_count,
                'tier1_subscribers_count': tier1_sub_count, 'tier2_subscribers_count': tier2_sub_count}

    class Meta:
        model = User
        fields = ['username', 'email', 'is_coach', 'is_subscriber', 'coach', 'subscriber', 'subscriber_data']


class PrerequisiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Prerequisite
        fields = ['description']


class MilestoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Milestone
        fields = ['description', 'id']
        read_only_fields = ['id']


class MilestoneCompletionReportSerializer(serializers.ModelSerializer):
    members = SubscriberSerializer(many=True)

    def create(self, validated_data):
        milestone_id = self.context['milestone_id']

        try:
            members = validated_data.pop('members')
        except KeyError:
            members = []

        milestone_report = MilestoneCompletionReport.objects.create(milestone_id=milestone_id, **validated_data)
        milestone_report.members.set(members)
        return milestone_report

    class Meta:
        model = MilestoneCompletionReport
        fields = ['members', 'message', 'milestone']
        read_only_fields = ['milestone']


class ProjectSerializer(serializers.ModelSerializer):
    prerequisites = PrerequisiteSerializer(many=True)
    milestones = MilestoneSerializer(many=True)
    difficulty = serializers.SerializerMethodField()

    def get_difficulty(self, obj):
        return obj.get_difficulty_display()

    class Meta:
        model = Project
        fields = ['name', 'description', 'difficulty', 'team_size', 'prerequisites', 'milestones']


class PostImageSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    def get_image(self, post_image):
        if post_image.image:
            return post_image.image.url
        return None

    class Meta:
        model = PostImage
        fields = ['height', 'width', 'image']


class PlaybackSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlaybackId
        fields = ['playback_id', 'policy']


class PostVideoSerializer(serializers.ModelSerializer):
    playback_ids = PlaybackSerializer(many=True)

    class Meta:
        model = PostVideo
        fields = ['asset_id', 'playback_ids']


class ReactObjectRelatedField(serializers.RelatedField):
    def to_representation(self, value):
        if isinstance(value, Post):
            serializer = PostSerializer(value)
        else:
            raise Exception('Unexpected type of tagged object')
        return serializer.data


class ReactSerializer(serializers.ModelSerializer):
    class Meta:
        model = React
        fields = ['type', 'user']


class PostSerializer(serializers.ModelSerializer):
    coach = CoachSerializer()
    linked_project = ProjectSerializer()
    images = PostImageSerializer(many=True)
    videos = PostVideoSerializer(many=True)
    reacted = serializers.SerializerMethodField()
    # reacts = ReactSerializer()
    reacts = serializers.SerializerMethodField()

    def get_reacted(self, post):
        user = self.context['request'].user
        if user.reacts.filter(object_id=post.id, user=user).exists():
            return True
        return False

    def get_reacts(self, post):
        return post.reacts.count()

    class Meta:
        model = Post
        fields = ['text', 'coach', 'images', 'videos', 'tiers', 'chained_posts', 'id', 'linked_project', 'reacted',
                  'reacts']

    def get_fields(self):
        fields = super(PostSerializer, self).get_fields()
        fields['chained_posts'] = PostSerializer(many=True)
        return fields


class PostNoChainSerializer(serializers.ModelSerializer):
    linked_project = ProjectSerializer()
    images = PostImageSerializer(many=True)
    videos = PostVideoSerializer(many=True)

    class Meta:
        model = Post
        fields = ['text', 'images', 'videos', 'id', 'linked_project']


class PostCreateSerializer(serializers.ModelSerializer):
    coach = CoachSerializer(required=False)

    def get_fields(self):
        fields = super(PostCreateSerializer, self).get_fields()
        fields['chained_posts'] = PostSerializer(many=True, required=False)
        return fields

    class Meta:
        model = Post
        fields = ['text', 'images', 'videos', 'tiers', 'id', 'linked_project', 'chained_posts', 'coach']
        read_only_fields = ['id', 'chained_posts', 'coach', 'videos', 'reacted', 'reacts']

    def create(self, validated_data):

        coach = self.context['request'].user.coach

        try:
            images = validated_data.pop('images')
        except KeyError:
            images = []

        try:
            tiers = validated_data.pop('tiers')
        except KeyError:
            tiers = []

        post = Post.objects.create(coach=coach, **validated_data)
        post.images.set(images)
        post.tiers.set(tiers)

        return post


class ChainedPostsSerializer(serializers.Serializer):
    posts = PostNoChainSerializer(many=True)

    def create(self, validated_data):
        coach = self.context['request'].user.coach
        results = {
            'posts': []
        }
        main_post = Post.objects.none()
        posts = validated_data.pop('posts')
        for i, post in enumerate(posts):

            # check if images exist then pop it from validation
            images = []
            try:
                images = post.pop('images')
            except KeyError:
                pass

            new_post = Post.objects.create(coach=coach, **post)

            # assign first post
            if i == 0:
                main_post = new_post
            # then chain the rest to the main post
            else:
                main_post.chained_posts.add(new_post)

            # set previously popped images
            new_post.images.set(images)

            results['posts'].append(new_post)
        return results

    def update(self, instance, validated_data):
        pass


class ChainPostsSerializer(serializers.Serializer):
    post_ids = serializers.JSONField()

    def create(self, validated_data):
        ids = validated_data['post_ids']  # .split(",")

        # convert all string ids to integers
        # ids = list(map(lambda item: int(item), ids))

        # get initial post to chain the rest
        main_post = Post.objects.get(pk=ids[0])

        # for each id chain it to the main_post
        for _id in ids:

            # ignore the first id
            if _id != ids[0]:
                post = Post.objects.get(pk=_id)
                main_post.chained_posts.add(post)

        return {"post_ids": ids}

    def update(self, instance, validated_data):
        pass


class CoachNewPosts(serializers.Serializer):
    coach = serializers.SerializerMethodField()
    new_posts = serializers.SerializerMethodField()

    def get_coach(self, coach):
        return CoachSerializer(coach, context={'request': self.context['request']}).data

    def get_new_posts(self, coach):
        return PostSerializer(coach.posts.exclude(parent_post__isnull=False),
                              context={'request': self.context['request']}, many=True).data

    def create(self, validated_data):
        pass

    def update(self, instance, validated_data):
        pass

    class Meta:
        fields = ['coach', 'new_posts']
        read_only_fields = fields


class NewPostsSerializer(serializers.Serializer):
    posts_per_coach = serializers.SerializerMethodField()

    def get_posts_per_coach(self, coach):
        return CoachNewPosts(coach).data

    def create(self, validated_data):
        pass

    def update(self, instance, validated_data):
        pass

    class Meta:
        fields = ['posts_per_coach']
        read_only_fields = fields


class CommentImageSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    def get_image(self, comment_image):
        if comment_image.image:
            return comment_image.image.url
        return None

    class Meta:
        model = CommentImage
        fields = ['height', 'width', 'image']


class CommentSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    images = CommentImageSerializer(many=True)

    class Meta:
        model = Comment
        fields = ['text', 'images', 'user']


class CreateCommentSerializer(serializers.ModelSerializer):
    user = UserSerializer(required=False)
    images = CommentImageSerializer(many=True, required=False)

    def create(self, validated_data):
        user = self.context['request'].user

        try:
            images = validated_data.pop('images')
        except KeyError:
            images = []
        comment = Comment.objects.create(user=user, **validated_data)
        comment.images.set(images)

        return comment

    class Meta:
        model = Comment
        fields = ['text', 'images', 'user', 'post']
        read_only_fields = ['user']


class MyProjectsSerializer(serializers.ModelSerializer):
    prerequisites = PrerequisiteSerializer(many=True)
    difficulty = serializers.SerializerMethodField()
    milestones = serializers.SerializerMethodField()
    my_team = serializers.SerializerMethodField()

    def get_my_team(self, project):
        user = self.context['request'].user
        if user:
            team = user.subscriber.teams.filter(project=project).first()
            return TeamSerializer(team).data
        return None

    def get_milestones(self, project):
        user = self.context['request'].user
        team = user.subscriber.teams.filter(project=project).first()
        _milestones = []

        for milestone in project.milestones.all():
            completed = False
            reports = milestone.reports.all()
            if team in milestone.completed_teams.all():
                completed = True
            status = None
            if reports.filter(status=MilestoneCompletionReport.ACCEPTED).exists():
                status = 'accepted'
            elif reports.filter(status=MilestoneCompletionReport.REJECTED).exists():
                status = 'rejected'
            elif reports.filter(status=MilestoneCompletionReport.PENDING).exists():
                status = 'pending'

            _milestones.append({'description': milestone.description, 'completed': completed,
                                'status': status, 'id': milestone.id,
                                'reports': MilestoneCompletionReportSerializer(reports, many=True).data})
        return _milestones

    def get_difficulty(self, obj):
        return obj.get_difficulty_display()

    class Meta:
        model = Project
        fields = ['name', 'description', 'difficulty', 'team_size', 'my_team', 'prerequisites', 'milestones', 'id']
        read_only_fields = ['id', 'my_team']


class TeamSerializer(serializers.ModelSerializer):
    members = SubscriberSerializer(many=True)
    project = serializers.StringRelatedField()

    class Meta:
        model = Team
        fields = ['name', 'avatar', 'project', 'members']


class ExpertiseAvatarSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    def get_image(self, expertise_avatar):
        if expertise_avatar.image:
            return expertise_avatar.image.url
        return None

    class Meta:
        model = ExpertiseFieldAvatar
        fields = ['width', 'height', 'image']


class ExpertiseSerializer(serializers.ModelSerializer):
    avatar = ExpertiseAvatarSerializer()

    class Meta:
        model = ExpertiseField
        fields = ['name', 'avatar']


class TierSerializer(serializers.ModelSerializer):
    tier_full = serializers.SerializerMethodField()

    def get_tier_full(self, obj):
        return obj.get_tier_display()

    class Meta:
        model = Tier
        fields = ['id', 'tier', 'tier_full', 'label', 'subheading', 'credit']


class ChatRoomSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()

    def get_id(self, chat_room):
        return chat_room.surrogate

    class Meta:
        model = ChatRoom
        fields = ['id', 'name', 'type', 'members', 'project']


class MessageSerializer(serializers.ModelSerializer):
    user = SubscriberSerializer()
    id = serializers.SerializerMethodField()

    def get_id(self, message):
        return message.surrogate

    class Meta:
        model = Message
        fields = ['text', 'created', 'user', 'id']
